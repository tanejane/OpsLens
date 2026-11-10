"""Stage 5.9: Offline marketing-agent regression tests."""

import copy
import unittest
from decimal import Decimal

from agent.investigation_state import InvestigationState
from agent.marketing_followup import (
    MarketingRejected,
    accounting,
    analyze,
    compile_plan,
    eligible,
    validate,
)
from agent.evidence_followup import candidates, extend


def finance_result():
    return {
        "route": "investigation",
        "status": "EVIDENCE_RANKED_NOT_CAUSAL",
        "executable": True,
        "causal_claim": False,
        "reason": "Contribution profit declined.",
        "limitations": [],
        "adaptive": {
            "stop_reason": "NO_MORE_APPROVED_HYPOTHESIS_TOOLS"
        },
        "driver_discovery": {
            "status": "RECONCILED_COMPONENT_BREAKDOWN",
            "period_evidence": {
                "before": {
                    "period": ["2018-02-01", "2018-03-01"]
                },
                "after": {
                    "period": ["2018-03-01", "2018-04-01"]
                },
            },
            "components": [{
                "component": "marketing_cost_effective",
                "before": "91937.69",
                "after": "141228.93",
                "delta": "49291.24",
            }],
        },
        "hypothesis_evaluation": {
            "status": "EVIDENCE_RANKED_NOT_CAUSAL",
            "premise_confirmed": True,
            "causal_claim": False,
            "hypotheses": [{
                "hypothesis_id":
                    "financial_component:marketing_cost_effective",
                "disposition": "SUPPORTS_PROFIT_PRESSURE",
            }],
        },
    }


def campaign_rows():
    return [
        {
            "campaign_id": "CMP_GROWTH_01",
            "before_spend": "0",
            "after_spend": "80000.00",
            "before_rows": 0,
            "after_rows": 20,
            "before_dates": 0,
            "after_dates": 20,
        },
        {
            "campaign_id": "CMP_011",
            "before_spend": "0",
            "after_spend": "61228.93",
            "before_rows": 0,
            "after_rows": 26,
            "before_dates": 0,
            "after_dates": 26,
        },
        {
            "campaign_id": "CMP_023",
            "before_spend": "27230.50",
            "after_spend": "0",
            "before_rows": 8,
            "after_rows": 0,
            "before_dates": 8,
            "after_dates": 0,
        },
        {
            "campaign_id": "CMP_017",
            "before_spend": "64707.19",
            "after_spend": "0",
            "before_rows": 18,
            "after_rows": 0,
            "before_dates": 18,
            "after_dates": 0,
        },
    ]


def reader_result(rows=None):
    return {"rows": [{"campaigns": (
        copy.deepcopy(rows) if rows is not None else campaign_rows()
    )}]}


class MarketingFollowupTests(unittest.IsolatedAsyncioTestCase):

    def new_state(self, max_steps=4):
        state = InvestigationState(max_steps=max_steps)
        state.begin(
            "initial_governed_investigation",
            "Initial investigation",
        )
        state.trace[-1]["decision"] = "COMPLETED"
        return state

    def test_01_eligible_finance_evidence_selects_action(self):
        initial = finance_result()

        self.assertTrue(eligible(initial))
        self.assertEqual(
            candidates(initial, set())[0][0],
            "marketing_campaign_composition",
        )

        self.assertEqual(
            candidates(
                initial, {"marketing_campaign_composition"}
            ),
            [],
        )

    def test_02_valid_campaigns_reconcile(self):
        initial = finance_result()
        plan = compile_plan(initial)
        proof = validate(
            initial,
            plan,
            reader_result(),
        )

        self.assertEqual(
            Decimal(proof["spend_change"]),
            Decimal("49291.24"),
        )
        self.assertEqual(
            proof["campaign_day_rows"],
            [26, 46],
        )
        self.assertEqual(len(proof["campaigns"]), 4)
        self.assertFalse(proof["causal_claim"])
        self.assertFalse(
            proof["independent_mechanism_verified"]
        )

    async def test_03_agent_executes_and_records_followup(self):
        initial = finance_result()
        state = self.new_state()
        calls = []

        async def reader(sql, purpose):
            calls.append((sql, purpose))
            return reader_result()

        output = await extend(initial, reader, state)

        self.assertEqual(len(calls), 1)
        self.assertIn(
            "marketing.spend_daily",
            calls[0][0],
        )
        self.assertEqual(
            output["marketing_analysis"]["status"],
            "DESCRIPTIVE_RECONCILED",
        )
        self.assertEqual(
            output["orchestration"]["stop_reason"],
            "MARKETING_FOLLOWUP_COMPLETED",
        )
        self.assertEqual(
            state.trace[-1]["decision"],
            "VALIDATED",
        )
        self.assertFalse(output["causal_claim"])
        self.assertNotIn("marketing_analysis", initial)

    def test_04_duplicate_campaign_day_rejected(self):
        initial = finance_result()
        rows = campaign_rows()
        rows[0]["after_rows"] = 21

        with self.assertRaises(MarketingRejected):
            validate(
                initial,
                compile_plan(initial),
                reader_result(rows),
            )

    def test_05_contradictory_spend_rejected(self):
        initial = finance_result()
        rows = campaign_rows()
        rows[0]["after_spend"] = "99999"

        with self.assertRaisesRegex(
            MarketingRejected,
            "contradicts",
        ):
            validate(
                initial,
                compile_plan(initial),
                reader_result(rows),
            )

    def test_06_missing_period_coverage_rejected(self):
        initial = finance_result()
        rows = campaign_rows()

        for row in rows:
            row["before_spend"] = "0"
            row["before_rows"] = 0
            row["before_dates"] = 0

        with self.assertRaises(MarketingRejected):
            validate(
                initial,
                compile_plan(initial),
                reader_result(rows),
            )

    def test_07_unsupported_or_causal_evidence_not_selected(self):
        for change in (
            {"causal_claim": True},
            {"executable": False},
            {"status": "UNVERIFIED"},
        ):
            with self.subTest(change=change):
                initial = finance_result()
                initial.update(change)

                self.assertFalse(eligible(initial))
                self.assertEqual(
                    candidates(initial, set()),
                    [],
                )

        initial = finance_result()
        initial["driver_discovery"]["components"][0][
            "delta"
        ] = "0"

        self.assertFalse(eligible(initial))

    async def test_08_tool_failure_preserves_initial_findings(self):
        initial = finance_result()
        state = self.new_state()

        async def failing_reader(sql, purpose):
            raise RuntimeError("Simulated unavailable tool")

        output = await extend(
            initial,
            failing_reader,
            state,
        )

        self.assertEqual(
            output["orchestration"]["stop_reason"],
            "FOLLOWUP_UNAVAILABLE_OR_CONTRADICTORY",
        )
        self.assertEqual(
            state.trace[-1]["decision"],
            "REJECTED_OR_FAILED",
        )
        self.assertEqual(
            output["driver_discovery"],
            initial["driver_discovery"],
        )
        self.assertNotIn("marketing_analysis", output)

    async def test_09_step_budget_blocks_marketing_action(self):
        initial = finance_result()
        state = self.new_state(max_steps=1)
        calls = []

        async def reader(sql, purpose):
            calls.append(sql)
            return reader_result()

        output = await extend(
            initial,
            reader,
            state,
        )

        self.assertEqual(calls, [])
        self.assertEqual(
            output["orchestration"]["stop_reason"],
            "STEP_BUDGET_REACHED",
        )
        self.assertNotIn("marketing_analysis", output)

    def test_10_plan_tampering_rejected(self):
        initial = finance_result()
        plan = compile_plan(initial)
        plan["sql"] += " "

        with self.assertRaises(MarketingRejected):
            validate(
                initial,
                plan,
                reader_result(),
            )


if __name__ == "__main__":
    unittest.main()
