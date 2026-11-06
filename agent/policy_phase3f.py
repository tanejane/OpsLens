
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal


ToolType = Literal[
    "get_metric_definition",
    "describe_relation",
    "run_readonly_sql",
    "search_knowledge",
]


@dataclass(frozen=True)
class NextAction:
    action_id: str
    hypothesis_id: str | None
    tool_name: ToolType
    purpose: str
    arguments: dict[str, Any]


DATE_COLUMN_CANDIDATES = [
    "business_date",
    "date",
    "spend_date",
    "order_date",
    "order_purchase_date",
    "order_purchase_timestamp",
    "created_at",
    "event_date",
]

MARKETING_COLUMN_CANDIDATES = [
    "marketing_cost",
    "marketing_spend",
    "spend",
    "actual_spend",
    "daily_spend",
    "media_spend",
]

REFUND_COLUMN_CANDIDATES = [
    "refunds",
    "refund_amount",
    "refund_value",
    "refunded_amount",
]


def _pick(columns: list[str], candidates: list[str]) -> str | None:
    lower = {c.lower(): c for c in columns}

    for candidate in candidates:
        if candidate.lower() in lower:
            return lower[candidate.lower()]

    return None


class DynamicInvestigationPolicy:
    """
    Schema-adaptive dynamic investigation policy.

    Both date and metric columns are selected from the governed schema.
    Failed actions are remembered and never blindly repeated.
    """

    def choose_next(self, state: dict[str, Any]) -> NextAction | None:
        ledger = state["evidence_ledger"]
        hypotheses = state["hypotheses"]
        failed = set(state.get("failed_action_ids", []))

        evidence_ids = {
            item["evidence_id"]
            for item in ledger
        }

        if "E-METRIC-DEFINITION" not in evidence_ids and "METRIC_DEF" not in failed:
            return NextAction(
                "METRIC_DEF",
                None,
                "get_metric_definition",
                "Understand contribution profit semantics.",
                {"metric_name": "contribution_profit"},
            )

        if "E-OUTCOME" not in evidence_ids and "OUTCOME" not in failed:
            return NextAction(
                "OUTCOME",
                None,
                "run_readonly_sql",
                "Confirm the reported profitability deterioration.",
                {
                    "query": """
                        SELECT
                            DATE_TRUNC('month', business_date)::date AS business_month,
                            SUM(revenue) AS revenue,
                            SUM(contribution_profit) AS contribution_profit,
                            SUM(contribution_profit)
                                / NULLIF(SUM(revenue),0) AS contribution_margin
                        FROM semantic.daily_commerce
                        WHERE business_date >= DATE '2018-02-01'
                          AND business_date < DATE '2018-04-01'
                        GROUP BY 1
                        ORDER BY 1
                    """,
                    "purpose": "Confirm the flagship outcome pattern.",
                    "expected_grain": "one row per business month",
                    "max_rows": 12,
                },
            )

        if hypotheses["H1"]["status"] == "UNTESTED" and "H1_STRUCTURED" not in failed:
            return NextAction(
                "H1_STRUCTURED",
                "H1",
                "run_readonly_sql",
                "Test supplier/COGS pressure.",
                {
                    "query": """
                        SELECT
                            DATE_TRUNC(
                                'month',
                                NULLIF(order_purchase_timestamp,'')::timestamp
                            )::date AS business_month,
                            SUM(effective_revenue) AS revenue,
                            SUM(effective_cogs) AS cogs
                        FROM semantic.order_economics
                        WHERE NULLIF(order_purchase_timestamp,'')::timestamp
                              >= DATE '2018-02-01'
                          AND NULLIF(order_purchase_timestamp,'')::timestamp
                              < DATE '2018-04-01'
                        GROUP BY 1
                        ORDER BY 1
                    """,
                    "purpose": "Compare COGS growth with revenue growth.",
                    "expected_grain": "one row per business month",
                    "max_rows": 12,
                },
            )

        if (
            hypotheses["H1"]["status"] == "SUPPORTED"
            and "E-H1-DOC" not in evidence_ids
            and "H1_DOC" not in failed
        ):
            return NextAction(
                "H1_DOC",
                "H1",
                "search_knowledge",
                "Find corroborating supplier-cost documentation.",
                {
                    "query": "supplier costs increased during March profitability decline",
                    "top_k": 3,
                },
            )

        if (
            hypotheses["H2"]["status"] == "UNTESTED"
            and "E-H2-SCHEMA" not in evidence_ids
            and "H2_SCHEMA" not in failed
        ):
            return NextAction(
                "H2_SCHEMA",
                "H2",
                "describe_relation",
                "Discover finance.daily_pnl fields before marketing analysis.",
                {
                    "schema": "finance",
                    "relation": "daily_pnl",
                },
            )

        if (
            hypotheses["H2"]["status"] == "UNTESTED"
            and "E-H2-SCHEMA" in evidence_ids
            and "H2_STRUCTURED" not in failed
        ):
            schema_evidence = next(
                e for e in ledger
                if e["evidence_id"] == "E-H2-SCHEMA"
            )

            columns = schema_evidence["value"]["columns"]
            date_col = _pick(columns, DATE_COLUMN_CANDIDATES)
            metric_col = _pick(columns, MARKETING_COLUMN_CANDIDATES)

            if date_col is None or metric_col is None:
                return None

            return NextAction(
                "H2_STRUCTURED",
                "H2",
                "run_readonly_sql",
                f"Test marketing economics using {date_col} and {metric_col}.",
                {
                    "query": f"""
                        SELECT
                            DATE_TRUNC(
                                'month',
                                NULLIF({date_col}::text,'')::timestamp
                            )::date AS business_month,
                            SUM(
                                COALESCE({metric_col}::double precision,0)
                            ) AS marketing_value
                        FROM finance.daily_pnl
                        WHERE NULLIF({date_col}::text,'')::timestamp
                              >= DATE '2018-02-01'
                          AND NULLIF({date_col}::text,'')::timestamp
                              < DATE '2018-04-01'
                        GROUP BY 1
                        ORDER BY 1
                    """,
                    "purpose": "Measure marketing cost across the deterioration window.",
                    "expected_grain": "one row per business month",
                    "max_rows": 12,
                },
            )

        if (
            hypotheses["H2"]["status"] == "SUPPORTED"
            and "E-H2-DOC" not in evidence_ids
            and "H2_DOC" not in failed
        ):
            return NextAction(
                "H2_DOC",
                "H2",
                "search_knowledge",
                "Find corroborating GrowthMax campaign documentation.",
                {
                    "query": "GrowthMax campaign spend incentives",
                    "top_k": 3,
                },
            )

        if hypotheses["H3"]["status"] == "UNTESTED" and "H3_STRUCTURED" not in failed:
            return NextAction(
                "H3_STRUCTURED",
                "H3",
                "run_readonly_sql",
                "Check product-mix incident overlap.",
                {
                    "query": "SELECT * FROM semantic.product_mix_effective",
                    "purpose": "Check controlled product-mix evidence window.",
                    "expected_grain": "controlled product-mix evidence row",
                    "max_rows": 1000,
                },
            )

        if (
            hypotheses["H4"]["status"] == "UNTESTED"
            and "E-H4-SCHEMA" not in evidence_ids
            and "H4_SCHEMA" not in failed
        ):
            return NextAction(
                "H4_SCHEMA",
                "H4",
                "describe_relation",
                "Discover finance.daily_pnl fields before refund analysis.",
                {
                    "schema": "finance",
                    "relation": "daily_pnl",
                },
            )

        if (
            hypotheses["H4"]["status"] == "UNTESTED"
            and "E-H4-SCHEMA" in evidence_ids
            and "H4_STRUCTURED" not in failed
        ):
            schema_evidence = next(
                e for e in ledger
                if e["evidence_id"] == "E-H4-SCHEMA"
            )

            columns = schema_evidence["value"]["columns"]
            date_col = _pick(columns, DATE_COLUMN_CANDIDATES)
            refund_col = _pick(columns, REFUND_COLUMN_CANDIDATES)

            if date_col is None or refund_col is None:
                return None

            return NextAction(
                "H4_STRUCTURED",
                "H4",
                "run_readonly_sql",
                f"Test refunds using {date_col} and {refund_col}.",
                {
                    "query": f"""
                        SELECT
                            DATE_TRUNC(
                                'month',
                                NULLIF({date_col}::text,'')::timestamp
                            )::date AS business_month,
                            SUM(
                                COALESCE({refund_col}::double precision,0)
                            ) AS refund_value
                        FROM finance.daily_pnl
                        WHERE NULLIF({date_col}::text,'')::timestamp
                              >= DATE '2018-02-01'
                          AND NULLIF({date_col}::text,'')::timestamp
                              < DATE '2018-04-01'
                        GROUP BY 1
                        ORDER BY 1
                    """,
                    "purpose": "Measure refunds across the deterioration window.",
                    "expected_grain": "one row per business month",
                    "max_rows": 12,
                },
            )

        return None
