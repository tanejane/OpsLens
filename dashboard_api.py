"""Thin monthly dashboard adapter over existing governed metric compilers.

No SQL is accepted from callers. Finance/order SQL comes only from the existing
Phase 4B.2 compiler; delivery and review use their validated Phase 4C compilers.
"""
from __future__ import annotations

import asyncio
import logging
import re
from datetime import date
from decimal import Decimal, InvalidOperation
from typing import Any

MONTH_RE = re.compile(r"^20\d{2}-(0[1-9]|1[0-2])$")
FINANCE_METRICS = ("revenue", "contribution_profit", "contribution_margin_pct", "orders")
logger = logging.getLogger("opslens.dashboard")


class DashboardUnavailable(RuntimeError):
    """Required governed source discovery could not reach MCP/PostgreSQL."""


def month_period(month: str) -> tuple[list[str], list[str]]:
    if not isinstance(month, str) or not MONTH_RE.fullmatch(month):
        raise ValueError("Month must use YYYY-MM format")
    year, month_num = map(int, month.split("-"))
    current_start = date(year, month_num, 1)
    current_end = date(year + (month_num == 12), 1 if month_num == 12 else month_num + 1, 1)
    previous_start = date(year - (month_num == 1), 12 if month_num == 1 else month_num - 1, 1)
    return ([previous_start.isoformat(), current_start.isoformat()],
            [current_start.isoformat(), current_end.isoformat()])


def numeric(value: Any) -> Decimal:
    if value is None or isinstance(value, bool):
        raise ValueError("No validated numeric value")
    try:
        parsed = Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError) as exc:
        raise ValueError("Invalid numeric result") from exc
    if not parsed.is_finite():
        raise ValueError("Non-finite numeric result")
    return parsed


def assemble_dashboard(month: str, current_period: list[str], previous_period: list[str],
                       measurements: dict[str, dict[str, Any]]) -> dict[str, Any]:
    """Compose validated readings and apply documented, descriptive movement rules."""
    metrics: dict[str, Any] = {}
    for metric_id in (*FINANCE_METRICS, "late_delivery_rate", "average_review_score"):
        record = measurements.get(metric_id, {})
        old = record.get("previous")
        new = record.get("current")
        if not isinstance(old, dict) or not isinstance(new, dict):
            metrics[metric_id] = {"status": "UNAVAILABLE", "reason": record.get("reason", "No validated measurement was returned for both periods.")}
            continue
        try:
            a = numeric(old.get("value")); b = numeric(new.get("value"))
        except ValueError:
            metrics[metric_id] = {"status": "UNAVAILABLE", "reason": record.get("reason", "A complete numeric measurement was not returned for both periods.")}
            continue
        unit = new.get("unit") or old.get("unit") or ""
        metrics[metric_id] = {
            "status": "MEASURED", "label": record.get("label", metric_id.replace("_", " ").title()),
            "definition": record.get("definition", "Governed metric definition."),
            "formula": record.get("formula"), "source": new.get("source") or old.get("source"),
            "unit": unit, "time_basis": new.get("time_basis") or old.get("time_basis"),
            "policy": new.get("policy") or old.get("policy"),
            "current": {**new, "period": current_period}, "previous": {**old, "period": previous_period},
            "delta": str(b - a), "delta_unit": "percentage_points" if unit in ("percent", "percentage") else "score_points" if unit == "score_1_to_5" else unit,
            "direction": "INCREASED" if b > a else "DECREASED" if b < a else "UNCHANGED",
            "limitations": list(dict.fromkeys([*record.get("limitations", []), *old.get("limitations", []), *new.get("limitations", [])])),
            "eligibility": {"previous": old.get("population"), "current": new.get("population")},
            "population_note": record.get("population_note", "Eligible source-row count is not returned by this aggregate metric contract."),
        }

    noteworthy: list[dict[str, Any]] = []
    revenue, profit = metrics["revenue"], metrics["contribution_profit"]
    if revenue["status"] == profit["status"] == "MEASURED" and revenue["direction"] == "INCREASED" and profit["direction"] == "DECREASED":
        noteworthy.append({"rule_id": "revenue_up_profit_down", "priority": "attention", "title": "Revenue increased while contribution profit declined", "metric_ids": ["revenue", "contribution_profit"], "disposition": "DESCRIPTIVE_MOVEMENT_NOT_CAUSAL", "causal_claim": False, "validated_incident": False})
    delivery, satisfaction = metrics["late_delivery_rate"], metrics["average_review_score"]
    if delivery["status"] == satisfaction["status"] == "MEASURED" and delivery["direction"] == "INCREASED" and satisfaction["direction"] == "DECREASED":
        noteworthy.append({"rule_id": "delivery_up_review_down", "priority": "attention", "title": "Late delivery rate increased while review score decreased", "metric_ids": ["late_delivery_rate", "average_review_score"], "disposition": "COINCIDENT_DESCRIPTIVE_MOVEMENT_NOT_CAUSAL", "causal_claim": False, "validated_incident": False})
    return {"status": "PARTIAL_MEASUREMENT" if any(v["status"] != "MEASURED" for v in metrics.values()) else "MEASURED",
            "month": month, "periods": {"previous": previous_period, "current": current_period},
            "metrics": metrics, "noteworthy_movements": noteworthy,
            "movement_rules": [
                {"rule_id": "revenue_up_profit_down", "definition": "Current revenue > previous revenue AND current contribution profit < previous contribution profit."},
                {"rule_id": "delivery_up_review_down", "definition": "Current late delivery rate > previous rate AND current average review score < previous score."},
            ], "limitations": ["Comparisons are between the selected calendar month and the immediately preceding calendar month.",
                              "A measured movement is descriptive and is not an automatically validated incident or causal explanation."]}


def _period_args(period: list[str]) -> tuple[str, str]:
    return period[0], period[1]


async def _finance_measure(client: Any, metric_id: str, period: list[str],
                           metadata: dict[str, dict[str, str]], approved: set[str], call: Any,
                           column_types: Any, metric_types: Any) -> dict[str, Any]:
    from agent.phase4b2_metric_governance import MetricRequest, compile_metric

    metric = metric_types[metric_id]
    source = metric.source
    schema, relation = source.split(".")
    columns = metadata.get(source)
    if columns is None:
        columns = column_types(await call(client, "describe_relation", {"schema": schema, "relation": relation}))
        metadata[source] = columns
    request = MetricRequest(metric=metric_id, start_date=period[0], end_date_exclusive=period[1], order="asc", limit=1)
    query = compile_metric(request, columns, approved)
    data = await call(client, "run_readonly_sql", {"query": query, "purpose": f"Governed dashboard metric: {metric_id}", "expected_grain": "one aggregate metric value for the selected calendar month", "max_rows": 1, "timeout_ms": 5000})
    rows = data.get("rows") if isinstance(data, dict) else None
    if not isinstance(rows, list) or len(rows) != 1 or not isinstance(rows[0], dict):
        raise ValueError("Finance metric did not return one validated aggregate row")
    value = numeric(rows[0].get("metric_value"))
    # COUNT(DISTINCT order_id) returns zero for an empty relation, which is not
    # evidence that the source has complete coverage for that month.
    if metric_id == "orders" and value == 0:
        raise ValueError("No source orders were available for the selected period")
    unit = "percent" if metric_id == "contribution_margin_pct" else "dataset_currency" if metric_id in ("revenue", "contribution_profit") else "orders"
    return {"value": str(value), "unit": unit, "source": source, "time_basis": metric.date_column,
            "definition": metric.meaning, "formula": metric.expression, "limitations": ["Descriptive aggregate; source coverage is not independently certified."]}


def _safe_unavailable_reason(exc: Exception, metric_id: str) -> str:
    reason = str(exc)
    if reason == "NO_SOURCE_COVERAGE":
        return "No source records were available in one or both selected months."
    if reason in ("NO_REVIEW_COVERAGE", "INSUFFICIENT_DELIVERY_EVIDENCE"):
        return "The source did not contain enough eligible evidence for one or both selected months."
    if reason == "No validated numeric value":
        return "The governed aggregate returned no numeric value for one or both selected months."
    if metric_id == "orders" and "No source orders" in reason:
        return "No source orders were available in one or both selected months."
    return ("The governed finance metric could not be measured for both selected periods."
            if metric_id in FINANCE_METRICS else
            "The governed operational metric could not be measured for both selected periods.")


async def load_dashboard(month: str) -> dict[str, Any]:
    previous_period, current_period = month_period(month)
    from mcp import Client
    from mcp_server.server import mcp
    from agent.phase4b1_semantic_playground import call, column_types, extract_relations
    from agent.phase4b2_metric_governance import METRICS as FINANCE_DEFINITIONS
    from agent.phase4c15_delivery import measure as delivery_measure
    from agent.phase4c11_satisfaction import measure as review_measure

    runtime_records: dict[str, dict[str, Any]] = {}
    errors: dict[str, str] = {}
    async with Client(mcp) as client:
        allowed: set[str] = set()
        successful_discoveries = 0
        for schema in {FINANCE_DEFINITIONS[m].source.split(".")[0] for m in FINANCE_METRICS}:
            try:
                rows = extract_relations(await call(client, "discover_schema", {"domain": schema}))
                successful_discoveries += 1
                for row in rows:
                    name = row if isinstance(row, str) else row.get("relation_name") or row.get("table_name") or row.get("name") or row.get("relation")
                    if name:
                        qualified = str(name) if "." in str(name) else f"{schema}.{name}"
                        if qualified.startswith(schema + "."):
                            allowed.add(qualified)
            except Exception:
                logger.exception("Governed dashboard source discovery failed for schema %s", schema)
                continue
        if successful_discoveries == 0:
            raise DashboardUnavailable("MCP/PostgreSQL source discovery failed for all required dashboard schemas")
        metadata: dict[str, dict[str, str]] = {}
        finance_jobs = [(metric_id, side, period) for metric_id in FINANCE_METRICS for side, period in (("previous", previous_period), ("current", current_period))]
        async def run_finance(metric_id: str, side: str, period: list[str]):
            try:
                reading = await _finance_measure(client, metric_id, period, metadata, allowed, call, column_types, FINANCE_DEFINITIONS)
                runtime_records.setdefault(metric_id, {})[side] = reading
            except Exception as exc:
                logger.exception("Dashboard finance measurement failed: metric=%s period=%s", metric_id, period)
                errors.setdefault(metric_id, _safe_unavailable_reason(exc, metric_id))
        await asyncio.gather(*(run_finance(*job) for job in finance_jobs))

        async def run_operational(metric_id: str, kind: str, side: str, period: list[str]):
            try:
                if kind == "delivery": reading = await delivery_measure(metric_id, *_period_args(period), lambda sql, purpose: _read(client, sql, purpose, call))
                else: reading = await review_measure(metric_id, *_period_args(period), lambda sql, purpose: _read(client, sql, purpose, call))
                runtime_records.setdefault(metric_id, {})[side] = {key: reading.get(key) for key in ("value", "unit", "source", "period", "population", "policy", "time_basis", "limitations")}
            except Exception as exc:
                logger.exception("Dashboard operational measurement failed: metric=%s period=%s", metric_id, period)
                errors.setdefault(metric_id, _safe_unavailable_reason(exc, metric_id))
        jobs = [("late_delivery_rate", "delivery", side, period) for side, period in (("previous", previous_period), ("current", current_period))]
        jobs += [("average_review_score", "review", side, period) for side, period in (("previous", previous_period), ("current", current_period))]
        await asyncio.gather(*(run_operational(*job) for job in jobs))

    labels = {"revenue": "Revenue", "contribution_profit": "Contribution profit", "contribution_margin_pct": "Contribution margin", "orders": "Orders", "late_delivery_rate": "Late delivery rate", "average_review_score": "Average review score"}
    definitions = {key: FINANCE_DEFINITIONS[key] for key in FINANCE_METRICS}
    records: dict[str, dict[str, Any]] = {}
    for metric_id, label in labels.items():
        finance_def = definitions.get(metric_id)
        records[metric_id] = {**runtime_records.get(metric_id, {}), "label": label,
            "definition": finance_def.meaning if finance_def else label,
            "formula": finance_def.expression if finance_def else None,
            "limitations": ["Currency is dataset-native and is not relabeled."] if metric_id in ("revenue", "contribution_profit") else [],
            "population_note": "Eligible source-row count is not returned by the governed finance aggregate." if finance_def else "Eligibility populations are shown from the validated metric result."}
        if metric_id in errors:
            records[metric_id]["reason"] = errors[metric_id]
        elif metric_id not in runtime_records:
            records[metric_id]["reason"] = "No governed reading was returned."
    result = assemble_dashboard(month, current_period, previous_period, records)
    for metric_id, metric in result["metrics"].items():
        if metric["status"] == "MEASURED" and metric_id not in ("revenue", "contribution_profit", "contribution_margin_pct", "orders"):
            metric["definition"] = {"late_delivery_rate": "Share of purchase-month eligible orders delivered after the estimated date.", "average_review_score": "Mean effective review score across reviewed orders in the purchase-month cohort."}[metric_id]
    return result


async def _read(client: Any, sql: str, purpose: str, call: Any) -> dict[str, Any]:
    data = await call(client, "run_readonly_sql", {"query": sql, "purpose": purpose, "expected_grain": "single governed monthly metric aggregate", "max_rows": 1, "timeout_ms": 5000})
    rows = data.get("rows") if isinstance(data, dict) else None
    if not isinstance(rows, list) or len(rows) != 1 or not isinstance(rows[0], dict):
        raise ValueError("Operational metric did not return one validated aggregate row")
    return rows[0]
