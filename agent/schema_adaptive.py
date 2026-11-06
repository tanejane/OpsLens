
from __future__ import annotations

from typing import Any

from agent.mcp_bridge import OpsLensMCPBridge


DATE_CANDIDATES = [
    "business_date",
    "date",
    "spend_date",
    "order_purchase_date",
    "order_purchase_timestamp",
    "return_date",
    "created_at",
    "event_date",
]

MARKETING_COST_CANDIDATES = [
    "marketing_cost",
    "marketing_spend",
    "spend",
    "actual_spend",
    "daily_spend",
    "media_spend",
]

REFUND_CANDIDATES = [
    "refunds",
    "refund_amount",
    "refund_value",
    "refunded_amount",
]

REVENUE_CANDIDATES = [
    "revenue",
    "effective_revenue",
]

CONTRIBUTION_CANDIDATES = [
    "contribution_profit",
    "effective_contribution_profit",
]


async def relation_columns(
    schema: str,
    relation: str,
) -> list[str]:
    bridge = OpsLensMCPBridge()
    result = await bridge.call(
        "describe_relation",
        {"schema": schema, "relation": relation},
    )

    if not result.get("ok"):
        raise RuntimeError(result.get("error") or "describe_relation failed")

    return [
        str(row["column_name"])
        for row in result["data"]
    ]


def first_present(
    columns: list[str],
    candidates: list[str],
) -> str | None:
    lower_map = {c.lower(): c for c in columns}

    for candidate in candidates:
        if candidate.lower() in lower_map:
            return lower_map[candidate.lower()]

    return None


async def monthly_metric(
    schema: str,
    relation: str,
    metric_candidates: list[str],
    start_date: str,
    end_date: str,
    purpose: str,
) -> dict[str, Any]:
    columns = await relation_columns(schema, relation)

    date_col = first_present(columns, DATE_CANDIDATES)
    metric_col = first_present(columns, metric_candidates)

    if not date_col or not metric_col:
        return {
            "ok": False,
            "error": (
                f"Could not identify required fields in {schema}.{relation}. "
                f"date_col={date_col}, metric_col={metric_col}, columns={columns}"
            ),
            "meta": {
                "schema": schema,
                "relation": relation,
                "columns": columns,
            },
        }

    query = f"""
        SELECT
            DATE_TRUNC(
                'month',
                NULLIF({date_col}::text, '')::timestamp
            )::date AS business_month,
            SUM(COALESCE({metric_col}::double precision, 0))
                AS metric_value
        FROM {schema}.{relation}
        WHERE NULLIF({date_col}::text, '')::timestamp >= DATE '{start_date}'
          AND NULLIF({date_col}::text, '')::timestamp < DATE '{end_date}'
        GROUP BY 1
        ORDER BY 1
    """

    bridge = OpsLensMCPBridge()
    result = await bridge.call(
        "run_readonly_sql",
        {
            "query": query,
            "purpose": purpose,
            "expected_grain": "one row per business month",
            "max_rows": 12,
        },
    )

    if result.get("ok"):
        result.setdefault("meta", {})
        result["meta"]["detected_date_column"] = date_col
        result["meta"]["detected_metric_column"] = metric_col

    return result
