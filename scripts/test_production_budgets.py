
"""OpsLens Stage 4.3 â€” Production budget controller tests.

Exercises the real InvestigationState implementation.
No Gemini, MCP server or PostgreSQL connections.

Run:
    python -m unittest scripts.test_production_budgets -v
"""

import unittest

from agent.investigation_state import InvestigationState, BudgetStop


class ProductionBudgetTests(unittest.IsolatedAsyncioTestCase):

    def test_01_new_state_has_remaining_time(self):
        state = InvestigationState()

        remaining = state.remaining()

        self.assertGreater(remaining, 0)
        self.assertLessEqual(remaining, 120)
        self.assertEqual(state.actions, set())

    def test_02_duplicate_action_is_blocked(self):
        state = InvestigationState()

        state.begin("verify_premise", "Initial evidence check")

        with self.assertRaises(BudgetStop):
            state.begin(
                "verify_premise",
                "Duplicate evidence check",
            )

        self.assertEqual(
            int("verify_premise" in state.actions),
            1,
        )

    def test_03_default_action_budget_is_enforced(self):
        state = InvestigationState()

        for index in range(4):
            state.begin(
                f"approved_action_{index}",
                "Controlled test action",
            )

        with self.assertRaises(BudgetStop):
            state.begin(
                "approved_action_4",
                "Would exceed action budget",
            )

        self.assertEqual(len(state.actions), 4)

    async def test_04_repeated_sql_uses_cached_result(self):
        state = InvestigationState()
        calls = []

        async def fake_reader():
            calls.append("executed")
            return {"ok": True, "rows": [123]}

        query = "SELECT 123 AS test_value"

        first = await state.read(query, fake_reader)
        second = await state.read(query, fake_reader)

        self.assertEqual(first, second)
        self.assertEqual(len(calls), 1)

    async def test_05_distinct_reads_respect_tool_budget(self):
        state = InvestigationState()
        calls = []

        async def fake_reader():
            calls.append("executed")
            return {"ok": True}

        # These are distinct synthetic SQL strings. The fake
        # reader never connects to an actual database.
        for index in range(40):
            await state.read(
                f"SELECT {index} AS test_value",
                fake_reader,
            )

        self.assertEqual(len(calls), 40)

        with self.assertRaises(BudgetStop):
            await state.read(
                "SELECT 999 AS test_value",
                fake_reader,
            )

        # A rejected request must not execute its reader.
        self.assertEqual(len(calls), 40)


if __name__ == "__main__":
    unittest.main()
