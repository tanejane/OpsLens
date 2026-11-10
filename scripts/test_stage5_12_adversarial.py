"""Stage 5.12B: adversarial agent decision-boundary tests.

Controlled responses, actual follow-up controller and validator.
No database, Gemini or production modifications.
"""

import copy
import unittest

from agent.evidence_followup import candidates, extend
from agent.investigation_state import InvestigationState
from scripts.test_marketing_followup import (
    finance_result,
    campaign_rows,
    reader_result,
)


class DecisionBoundaryTests(unittest.IsolatedAsyncioTestCase):

    def state(self, **budgets):
        state = InvestigationState(**budgets)
        state.begin(
            "initial_governed_investigation",
            "Initial governed investigation",
        )
        state.trace[-1]["decision"] = "COMPLETED"
        return state

    async def test_01_invalid_periods_do_not_trigger_action(self):
        result = finance_result()
        result["driver_discovery"]["period_evidence"]["after"][
            "period"
        ] = ["2018-05-01", "2018-06-01"]

        calls = []

        async def reader(sql, purpose):
            calls.append(sql)
            return reader_result()

        output = await extend(result, reader, self.state())

        self.assertEqual(calls, [])
        self.assertNotIn("marketing_analysis", output)
        self.assertEqual(candidates(result, set()), [])

    async def test_02_unsupported_pressure_does_not_trigger_action(self):
        result = finance_result()
        result["hypothesis_evaluation"]["hypotheses"][0][
            "disposition"
        ] = "NOT_SUPPORTED"

        calls = []

        async def reader(sql, purpose):
            calls.append(sql)
            return reader_result()

        output = await extend(result, reader, self.state())

        self.assertEqual(calls, [])
        self.assertNotIn("marketing_analysis", output)

    async def test_03_contradictory_totals_rejected(self):
        result = finance_result()
        rows = campaign_rows()
        rows[0]["after_spend"] = "90000"

        state = self.state()

        async def reader(sql, purpose):
            return reader_result(rows)

        output = await extend(result, reader, state)

        self.assertNotIn("marketing_analysis", output)
        self.assertEqual(
            output["driver_discovery"],
            result["driver_discovery"],
        )
        self.assertEqual(
            output["orchestration"]["stop_reason"],
            "FOLLOWUP_UNAVAILABLE_OR_CONTRADICTORY",
        )
        self.assertEqual(
            state.trace[-1]["error_type"],
            "MarketingRejected",
        )

    async def test_04_duplicate_campaign_day_rejected(self):
        result = finance_result()
        rows = campaign_rows()
        rows[0]["after_dates"] = 19

        state = self.state()

        async def reader(sql, purpose):
            return reader_result(rows)

        output = await extend(result, reader, state)

        self.assertNotIn("marketing_analysis", output)
        self.assertEqual(
            state.trace[-1]["decision"],
            "REJECTED_OR_FAILED",
        )

    async def test_05_unexpected_transport_rejected(self):
        result = finance_result()
        state = self.state()

        async def reader(sql, purpose):
            return {
                "campaigns": campaign_rows(),
                "untrusted_extra": True,
            }

        output = await extend(result, reader, state)

        self.assertNotIn("marketing_analysis", output)
        self.assertEqual(
            state.trace[-1]["error_type"],
            "MarketingRejected",
        )

    async def test_06_tool_budget_prevents_query(self):
        result = finance_result()
        state = self.state(max_tools=1)

        # Simulate the initial investigation having consumed
        # the only permitted tool call.
        state.tools = 1
        actual_queries = []

        async def reader(sql, purpose):
            async def operation():
                actual_queries.append(sql)
                return reader_result()

            return await state.read(sql, operation)

        output = await extend(result, reader, state)

        self.assertEqual(actual_queries, [])
        self.assertNotIn("marketing_analysis", output)
        self.assertEqual(
            output["orchestration"]["stop_reason"],
            "TOOL_BUDGET_REACHED",
        )

    async def test_07_causal_result_blocks_followup(self):
        result = finance_result()
        result["causal_claim"] = True

        calls = []

        async def reader(sql, purpose):
            calls.append(sql)
            return reader_result()

        output = await extend(result, reader, self.state())

        self.assertEqual(calls, [])
        self.assertNotIn("marketing_analysis", output)
        self.assertEqual(output["causal_claim"], True)

        # This test checks the follow-up gate only.
        # It does not certify the upstream causal result as safe.

    async def test_08_valid_control_still_succeeds(self):
        result = finance_result()
        state = self.state()
        calls = []

        async def reader(sql, purpose):
            calls.append(sql)
            return reader_result()

        output = await extend(result, reader, state)

        self.assertEqual(len(calls), 1)
        self.assertEqual(
            output["marketing_analysis"]["status"],
            "DESCRIPTIVE_RECONCILED",
        )
        self.assertFalse(
            output["marketing_analysis"][
                "independent_mechanism_verified"
            ]
        )
        self.assertEqual(
            state.trace[-1]["decision"],
            "VALIDATED",
        )


if __name__ == "__main__":
    unittest.main(verbosity=2)
