
"""OpsLens Stage 4.4 — Real deadline enforcement tests.

Uses production InvestigationState with a simulated monotonic clock.
No database, MCP, Gemini, or real waiting required.

Run:
    python -m unittest scripts.test_agent_deadlines -v
"""

import unittest

from agent.investigation_state import (
    InvestigationState,
    BudgetStop,
)


class FakeClock:
    def __init__(self, start=1000.0):
        self.current = start

    def __call__(self):
        return self.current

    def advance(self, seconds):
        self.current += seconds


class AgentDeadlineTests(unittest.IsolatedAsyncioTestCase):

    def make_state(self, seconds=10):
        clock = FakeClock()
        state = InvestigationState(
            seconds=seconds,
            clock=clock,
        )
        return state, clock

    def test_01_remaining_time_decreases(self):
        state, clock = self.make_state()

        self.assertEqual(state.remaining(), 10)

        clock.advance(3)

        self.assertEqual(state.remaining(), 7)

    def test_02_exact_deadline_is_rejected(self):
        state, clock = self.make_state()

        clock.advance(10)

        with self.assertRaisesRegex(
            BudgetStop, "DEADLINE_REACHED"
        ):
            state.remaining()

    def test_03_expired_deadline_blocks_action(self):
        state, clock = self.make_state()

        state.begin("initial_check", "Verify premise")

        clock.advance(11)

        with self.assertRaisesRegex(
            BudgetStop, "DEADLINE_REACHED"
        ):
            state.begin(
                "additional_check",
                "Would exceed the time budget",
            )

        self.assertEqual(
            state.actions,
            {"initial_check"},
        )
        self.assertEqual(len(state.trace), 1)

    async def test_04_expired_deadline_blocks_tool(self):
        state, clock = self.make_state()
        calls = []

        async def operation():
            calls.append("executed")
            return {"ok": True}

        clock.advance(11)

        with self.assertRaisesRegex(
            BudgetStop, "DEADLINE_REACHED"
        ):
            await state.read(
                "SELECT 1",
                operation,
            )

        self.assertEqual(calls, [])
        self.assertEqual(state.tools, 0)

    async def test_05_expired_operation_not_cached(self):
        state, clock = self.make_state()
        calls = []

        async def slow_operation():
            calls.append("executed")
            clock.advance(11)
            return {"ok": True, "value": 123}

        with self.assertRaisesRegex(
            BudgetStop, "DEADLINE_REACHED"
        ):
            await state.read(
                "SELECT 123",
                slow_operation,
            )

        self.assertEqual(calls, ["executed"])
        self.assertEqual(state.tools, 1)
        self.assertEqual(state.queries, {})

    async def test_06_cached_read_respects_deadline(self):
        state, clock = self.make_state()
        calls = []

        async def operation():
            calls.append("executed")
            return {"ok": True}

        await state.read("SELECT 1", operation)

        self.assertEqual(len(calls), 1)

        clock.advance(10)

        with self.assertRaisesRegex(
            BudgetStop, "DEADLINE_REACHED"
        ):
            await state.read("SELECT 1", operation)

        self.assertEqual(len(calls), 1)

    def test_07_invalid_budget_configuration(self):
        invalid_configs = [
            {"max_steps": 0},
            {"max_steps": 9},
            {"max_tools": 0},
            {"max_tools": 101},
            {"seconds": 0},
            {"seconds": 181},
            {"max_steps": True},
        ]

        for config in invalid_configs:
            with self.subTest(config=config):
                with self.assertRaises(ValueError):
                    InvestigationState(**config)

    def test_08_snapshot_records_limits_and_stop(self):
        state, clock = self.make_state()

        state.begin("initial_check", "Verify premise")

        clock.advance(10)

        with self.assertRaises(BudgetStop) as error:
            state.remaining()

        snapshot = state.snapshot(str(error.exception))

        self.assertEqual(
            snapshot["stop_reason"],
            "DEADLINE_REACHED",
        )
        self.assertEqual(snapshot["steps_used"], 1)
        self.assertEqual(snapshot["tools_used"], 0)
        self.assertEqual(snapshot["budgets"]["seconds"], 10)
        self.assertFalse(snapshot["causal_claim"])


if __name__ == "__main__":
    unittest.main()
