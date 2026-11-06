"""OpsLens Phase 4B: conservative, read-only investigation playground.

Scope: reviews in a specified month, revenue/profit, delivery timeliness.
All queries are application-owned, and run through the existing SQL MCP tool.
Other plans are returned with a clear unsupported-execution status.
"""
from __future__ import annotations

import asyncio
import calendar
import json
import re
from datetime import date
from typing import Any

from mcp import Client
from mcp_server.server import mcp
from agent.phase4a1_live_context import build_live_context
from agent.phase4a_planner import GeminiPlanProvider
from agent.phase4a_plan_contract import validate_plan


from agent.phase4b_playground_utils import (InvestigationUnavailable, month_window, previous_month, require_identifiers, num)


async def call(tool: str, args: dict) -> dict:
    async with Client(mcp) as client:
        result = await client.call_tool(tool, args)
    data = getattr(result, "structured_content", None)
    if getattr(result, "is_error", False) or not isinstance(data, dict):
        raise InvestigationUnavailable(f"MCP returned invalid {tool} response")
    if data.get("ok") is False or data.get("error"):
        raise InvestigationUnavailable(f"{tool}: {data.get('error')}")
    return data.get("data", data)




async def describe(relation: str) -> list[str]:
    schema, name = relation.split(".")
    data = await call("describe_relation", {"schema": schema, "relation": name})
    records = data.get("columns", data) if isinstance(data, dict) else data
    if not isinstance(records, list):
        raise InvestigationUnavailable(f"Unexpected metadata format for {relation}")
    cols = [r.get("column_name") or r.get("name") for r in records if isinstance(r, dict)]
    if not cols or any(not isinstance(c, str) for c in cols):
        raise InvestigationUnavailable(f"Invalid columns for {relation}")
    return cols


async def sql(query: str, purpose: str, grain: str) -> list[dict]:
    data = await call("run_readonly_sql", {
        "query": query, "purpose": purpose, "expected_grain": grain,
        "max_rows": 50, "timeout_ms": 10000,
    })
    rows = data.get("rows") if isinstance(data, dict) else None
    if not isinstance(rows, list):
        raise InvestigationUnavailable("SQL MCP response did not contain rows")
    return rows


def num(value: Any) -> float | None:
    try:
        return float(value) if value is not None else None
    except (ValueError, TypeError):
        return None


async def investigate_reviews(start: str, end: str) -> dict:
    """Outcome and delivery-association checks; no causal attribution from association."""
    relation_reviews = "cx.effective_reviews"
    relation_delivery = "operations.delivery_effective"
    rcols = await describe(relation_reviews)
    dcols = await describe(relation_delivery)
    require_identifiers(rcols, {"order_id", "effective_review_score"}, relation_reviews)
    require_identifiers(dcols, {
        "order_id", "order_purchase_timestamp", "order_estimated_delivery_date",
        "effective_delivered_customer_date"
    }, relation_delivery)
    prev = previous_month(start)
    # Review comparisons are explicitly defined by PURCHASE month, not review submission date.
    q1 = f"""
    SELECT DATE_TRUNC('month', NULLIF(d.order_purchase_timestamp::text,'')::timestamp)::date AS month,
           COUNT(r.order_id) AS reviews,
           AVG(r.effective_review_score::double precision) AS avg_review_score,
           AVG(CASE WHEN r.effective_review_score::double precision <= 2 THEN 1.0 ELSE 0.0 END) AS low_review_share
    FROM cx.effective_reviews r
    JOIN operations.delivery_effective d ON r.order_id = d.order_id
    WHERE NULLIF(d.order_purchase_timestamp::text,'')::timestamp >= DATE '{prev}'
      AND NULLIF(d.order_purchase_timestamp::text,'')::timestamp < DATE '{end}'
    GROUP BY 1 ORDER BY 1
    """
    outcome = await sql(q1, "Compare effective review scores by purchase cohort month", "purchase month")
    if len(outcome) < 2:
        raise InvestigationUnavailable("Insufficient monthly review observations")
    # Verify actual-vs-estimated lateness and its relationship to reviews.
    q2 = f"""
    SELECT DATE_TRUNC('month', NULLIF(d.order_purchase_timestamp::text,'')::timestamp)::date AS month,
           COUNT(*) AS reviewed_orders_with_delivery,
           AVG(CASE WHEN d.effective_delivered_customer_date > NULLIF(d.order_estimated_delivery_date::text,'')::timestamp THEN 1.0 ELSE 0.0 END) AS late_share,
           AVG(GREATEST(0, EXTRACT(EPOCH FROM (d.effective_delivered_customer_date - NULLIF(d.order_estimated_delivery_date::text,'')::timestamp)) / 86400.0)) AS avg_late_days,
           AVG(CASE WHEN d.effective_delivered_customer_date > NULLIF(d.order_estimated_delivery_date::text,'')::timestamp THEN r.effective_review_score::double precision END) AS late_order_review_score,
           AVG(CASE WHEN d.effective_delivered_customer_date <= NULLIF(d.order_estimated_delivery_date::text,'')::timestamp THEN r.effective_review_score::double precision END) AS ontime_order_review_score
    FROM operations.delivery_effective d
    JOIN cx.effective_reviews r ON d.order_id = r.order_id
    WHERE NULLIF(d.order_purchase_timestamp::text,'')::timestamp >= DATE '{prev}'
      AND NULLIF(d.order_purchase_timestamp::text,'')::timestamp < DATE '{end}'
      AND d.effective_delivered_customer_date IS NOT NULL
      AND NULLIF(d.order_estimated_delivery_date::text,'') IS NOT NULL
    GROUP BY 1 ORDER BY 1
    """
    delivery = await sql(q2, "Test timing and association of delivery lateness and reviews", "purchase month")
    a, b = outcome[-2], outcome[-1]
    delta = None if num(a.get("avg_review_score")) is None or num(b.get("avg_review_score")) is None else round(num(b["avg_review_score"]) - num(a["avg_review_score"]), 3)
    observed_decline = delta is not None and delta < 0
    delivery_change = None
    if len(delivery) >= 2 and num(delivery[-1].get("late_share")) is not None and num(delivery[-2].get("late_share")) is not None:
        delivery_change = round(100 * (num(delivery[-1]["late_share"]) - num(delivery[-2]["late_share"])), 2)
    return {
        "status": "partial_investigation",
        "cohort_definition": "Order purchase month; not review submission month",
        "outcome": {"monthly_review_summary": outcome, "review_score_delta": delta, "decline_confirmed": observed_decline},
        "delivery_evidence": {"monthly_delivery_review_summary": delivery, "late_share_change_pp": delivery_change},
        "hypotheses": [
            {"statement": "Delivery deterioration contributed to lower reviews", "status": "POSSIBLE_ASSOCIATION" if observed_decline and delivery_change is not None and delivery_change > 0 else "NOT_ESTABLISHED", "caveat": "Temporal coincidence/association is not causal proof; seller, region, and order-mix confounding untested."},
            {"statement": "Product defects caused lower reviews", "status": "UNTESTED", "caveat": "No linked defect or product-quality test executed."},
        ],
        "limitations": ["No defect attribution", "No causal impact decomposition", "Review sample and delivery sample differ when delivery dates are missing", "Purchase-month cohort is not the review-posting month"],
        "sources": [relation_reviews, relation_delivery],
    }


async def investigate_profit(start: str, end: str) -> dict:
    rel = "semantic.daily_commerce"
    cols = await describe(rel)
    require_identifiers(cols, {"business_date", "revenue", "contribution_profit"}, rel)
    prev = previous_month(start)
    rows = await sql(f"""
        SELECT DATE_TRUNC('month', business_date)::date AS month,
               SUM(revenue) AS revenue,
               SUM(contribution_profit) AS contribution_profit,
               SUM(contribution_profit)/NULLIF(SUM(revenue),0) AS contribution_margin
        FROM semantic.daily_commerce
        WHERE business_date >= DATE '{prev}' AND business_date < DATE '{end}'
        GROUP BY 1 ORDER BY 1
    """, "Verify revenue and contribution profit movements", "business month")
    return {"status":"outcome_verified_only", "monthly_outcome":rows,
            "hypotheses":[], "limitations":["Root causes not tested by this recipe"], "sources":[rel]}


async def run(question: str, *, provider=None) -> dict:
    packet, provenance = await build_live_context(question)
    plan_provider = provider or GeminiPlanProvider()
    plan = await asyncio.to_thread(plan_provider.create_plan, packet)
    validate_plan(plan, packet)
    base = {"question":question, "catalog_provenance":provenance, "plan":plan.model_dump()}
    if plan.date_ambiguity:
        return {**base, "execution":{"status":"needs_date", "message":"Explicit month and year are required for the first playground."}}
    try:
        start, end = month_window(question)
        if plan.investigation_type == "returns_cx" and "review" in question.lower():
            execution = await investigate_reviews(start, end)
        elif plan.investigation_type == "profitability":
            execution = await investigate_profit(start, end)
        else:
            execution = {"status":"unsupported_recipe", "message":"Plan created, but no governed execution recipe exists for this investigation yet. No SQL was executed."}
    except InvestigationUnavailable as exc:
        execution = {"status":"blocked", "reason":str(exc)}
    return {**base, "execution": execution}


def main() -> None:
    print("OpsLens — Phase 4B investigation playground (read-only)")
    print("Try: Why did customer reviews decline in June 2018?")
    print("Enter an empty line or 'exit' to quit.\n")
    while True:
        try:
            question = input("OpsLens > ").strip()
        except (EOFError, KeyboardInterrupt):
            break
        if not question or question.lower() in {"exit", "quit"}:
            break
        try:
            outcome = asyncio.run(run(question))
            print(json.dumps(outcome, indent=2, ensure_ascii=False, default=str))
        except Exception as exc:
            print(json.dumps({"status":"error", "detail":str(exc)}, ensure_ascii=False))
        print()


if __name__ == "__main__":
    main()
