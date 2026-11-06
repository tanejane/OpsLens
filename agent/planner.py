from __future__ import annotations
from dataclasses import dataclass

@dataclass(frozen=True)
class PlannedTest:
    test_id: str
    hypothesis_id: str | None
    purpose: str
    expected_grain: str
    query: str

class DeterministicBaselinePlanner:
    def plan_flagship_profitability_tests(self, question: str) -> list[PlannedTest]:
        return [
            PlannedTest(
                "OUTCOME",
                None,
                "Confirm revenue increased while contribution profit and margin deteriorated.",
                "one row per business month",
                """
                SELECT
                    DATE_TRUNC('month', business_date)::date AS business_month,
                    SUM(revenue) AS revenue,
                    SUM(contribution_profit) AS contribution_profit,
                    SUM(contribution_profit)/NULLIF(SUM(revenue),0) AS contribution_margin
                FROM semantic.daily_commerce
                WHERE business_date >= DATE '2018-02-01'
                  AND business_date < DATE '2018-04-01'
                GROUP BY 1
                ORDER BY 1
                """
            ),
            PlannedTest(
                "H1-COGS",
                "H1",
                "Test whether COGS grew faster than revenue from Feb to Mar 2018.",
                "one row per business month",
                """
                SELECT
                    DATE_TRUNC('month', NULLIF(order_purchase_timestamp,'')::timestamp)::date AS business_month,
                    SUM(effective_revenue) AS revenue,
                    SUM(effective_cogs) AS cogs,
                    SUM(effective_contribution_profit) AS contribution_profit
                FROM semantic.order_economics
                WHERE NULLIF(order_purchase_timestamp,'')::timestamp >= DATE '2018-02-01'
                  AND NULLIF(order_purchase_timestamp,'')::timestamp < DATE '2018-04-01'
                GROUP BY 1
                ORDER BY 1
                """
            )
        ]
