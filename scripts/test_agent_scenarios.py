
"""OpsLens Stage 4.2: evidence-driven agent loop evaluation.

Tests the real agent.evidence_followup.extend coordinator using
controlled tool responses. No database, network, or Gemini calls.

Run:
    python -m unittest scripts.test_agent_scenarios -v
"""

import copy
import unittest
from unittest.mock import patch

from agent.evidence_followup import extend, candidates
from agent.investigation_state import BudgetStop


PERIOD = ["2018-02-01", "2018-03-01"]


def initial_result(
    *,
    unclassified=0,
    missing_reviews=0,
    executable=True,
    causal_claim=False,
):
    """Minimal governed comparison fixture, not real observed data."""
    return {
        "route": "delivery_review_comparison",
        "status": "COMPARISON_MEASURED_WITH_SCOPE_LIMITS",
        "executable": executable,
        "causal_claim": causal_claim,
        "reason": "Descriptive delivery and review comparison.",
        "limitations": ["The comparison is not causal evidence."],
        "evidence": {
            "period": PERIOD.copy(),
            "total_orders": 10,
            "missing_review_rows": missing_reviews,
            "cohorts": {
                "late": {"orders": 2},
                "on_time": {"orders": 8 - unclassified},
                "unclassified": {"orders": unclassified},
            },
        },
    }


def delivery_proof(*, valid=True):
    """Controlled response from the registered delivery executor."""
    return {
        "period": PERIOD.copy(),
        "causal_claim": False,
        "source": "fixture.delivery",
        "value": 70.0,
        "population": {
            "eligible_orders": 10 if valid else 11,
            "late_orders": 2,
            "lateness_eligible_orders": 9,
            "missing_actual": 2,
            "missing_estimated": 1,
        },
    }


def review_proof():
    return {
        "period": PERIOD.copy(),
        "causal_claim": False,
        "source": "fixture.review",
        "value": 50.0,
        "population": {
            "eligible_orders": 10,
            "reviewed_orders": 5,
        },
    }


class ControlledState:
    """A test double for budget and trace recording.

    The production extend() method is real. This is only a
    controlled representation of its state interface.
    """

    def __init__(self, max_actions=4, fail_on_remaining=False):
        self.max_actions = max_actions
        self.fail_on_remaining = fail_on_remaining
        self.actions = []
        self.trace = []

    def remaining(self):
        if self.fail_on_remaining:
            raise BudgetStop("DEADLINE_REACHED")
        return 60.0

    def begin(self, action, reason):
        if len(self.actions) >= self.max_actions:
            raise BudgetStop("ACTION_BUDGET_EXHAUSTED")
        if action in self.actions:
            raise BudgetStop("DUPLICATE_ACTION")
        self.actions.append(action)
        self.trace.append({
            "capability": action,
            "reason": reason,
            "decision": "STARTED",
        })

    def snapshot(self, stop_reason):
        return {
            "trace": copy.deepcopy(self.trace),
            "stop_reason": stop_reason,
            "actions_used": len(self.actions),
        }


class AgentScenarioTests(unittest.IsolatedAsyncioTestCase):

    async def asyncSetUp(self):
        self.calls = []

        async def delivery(metric, *args):
            self.calls.append(("delivery", metric))
            return delivery_proof()

        async def review(metric, *args):
            self.calls.append(("review", metric))
            return review_proof()

        self.delivery = delivery
        self.review = review

        # Replace only the executor functions; candidate selection,
        # loop control and proof validation remain production code.
        self.registry = patch.dict(
            "agent.evidence_followup.REGISTRY",
            {
                "delivery_missingness": (
                    "delivery_evidence_coverage",
                    self.delivery,
                ),
                "review_population_coverage": (
                    "review_coverage",
                    self.review,
                ),
            },
        )
        self.registry.start()

    async def asyncTearDown(self):
        self.registry.stop()

    @staticmethod
    async def reader(*args):
        raise AssertionError(
            "Fixture executor must not invoke a real SQL reader"
        )

    async def test_01_no_gap_stops_without_tools(self):
        original = initial_result()
        state = ControlledState()

        result = await extend(original, self.reader, state)

        self.assertEqual(state.actions, [])
        self.assertEqual(self.calls, [])
        self.assertEqual(
            result["orchestration"]["stop_reason"],
            "QUESTION_ADDRESSED",
        )
        self.assertNotIn("supporting_analyses", result)
        self.assertEqual(original, initial_result())

    async def test_02_missing_delivery_selects_approved_action(self):
        original = initial_result(unclassified=1)
        state = ControlledState()

        result = await extend(original, self.reader, state)

        self.assertEqual(
            state.actions,
            ["delivery_missingness"],
        )
        self.assertEqual(len(self.calls), 1)
        self.assertEqual(
            state.trace[0]["decision"],
            "VALIDATED",
        )
        self.assertEqual(
            result["supporting_analyses"][0]["capability"],
            "delivery_missingness",
        )
        self.assertFalse(result["causal_claim"])

    async def test_03_two_gaps_trigger_two_distinct_actions(self):
        original = initial_result(
            unclassified=1,
            missing_reviews=2,
        )
        state = ControlledState()

        result = await extend(original, self.reader, state)

        self.assertEqual(
            state.actions,
            [
                "delivery_missingness",
                "review_population_coverage",
            ],
        )
        self.assertEqual(len(self.calls), 2)
        self.assertTrue(
            all(
                step["decision"] == "VALIDATED"
                for step in state.trace
            )
        )
        self.assertEqual(
            len(result["supporting_analyses"]), 2
        )
        self.assertEqual(
            result["orchestration"]["stop_reason"],
            "QUESTION_ADDRESSED",
        )

        # The approved actions are now exhausted.
        self.assertEqual(
            candidates(result, state.actions), []
        )

    async def test_04_contradictory_population_is_rejected(self):
        async def contradictory(metric, *args):
            self.calls.append(("delivery", metric))
            return delivery_proof(valid=False)

        with patch.dict(
            "agent.evidence_followup.REGISTRY",
            {
                "delivery_missingness": (
                    "delivery_evidence_coverage",
                    contradictory,
                ),
            },
        ):
            original = initial_result(unclassified=1)
            state = ControlledState()
            result = await extend(
                original, self.reader, state
            )

        self.assertEqual(
            state.trace[-1]["decision"],
            "REJECTED_OR_FAILED",
        )
        self.assertEqual(
            result["orchestration"]["stop_reason"],
            "FOLLOWUP_UNAVAILABLE_OR_CONTRADICTORY",
        )
        self.assertNotIn("supporting_analyses", result)
        self.assertEqual(
            result["evidence"], original["evidence"]
        )

    async def test_05_tool_failure_stops_safely(self):
        async def broken_executor(metric, *args):
            self.calls.append(("delivery", metric))
            raise RuntimeError("Simulated fixture failure")

        with patch.dict(
            "agent.evidence_followup.REGISTRY",
            {
                "delivery_missingness": (
                    "delivery_evidence_coverage",
                    broken_executor,
                ),
            },
        ):
            original = initial_result(unclassified=1)
            state = ControlledState()
            result = await extend(
                original, self.reader, state
            )

        self.assertEqual(len(self.calls), 1)
        self.assertEqual(
            state.trace[-1]["error_type"],
            "RuntimeError",
        )
        self.assertEqual(
            result["orchestration"]["stop_reason"],
            "FOLLOWUP_UNAVAILABLE_OR_CONTRADICTORY",
        )
        self.assertNotIn("supporting_analyses", result)
        self.assertIn(
            "additional investigation could not be completed",
            " ".join(result["limitations"]).lower(),
        )

    async def test_06_budget_exhaustion_prevents_tool_call(self):
        original = initial_result(unclassified=1)
        state = ControlledState(max_actions=0)

        result = await extend(original, self.reader, state)

        self.assertEqual(self.calls, [])
        self.assertEqual(state.actions, [])
        self.assertEqual(
            result["orchestration"]["stop_reason"],
            "ACTION_BUDGET_EXHAUSTED",
        )
        self.assertNotIn("supporting_analyses", result)

    async def test_07_unverified_causal_result_does_not_extend(self):
        original = initial_result(
            unclassified=1,
            causal_claim=True,
        )
        state = ControlledState()

        result = await extend(original, self.reader, state)

        self.assertEqual(self.calls, [])
        self.assertEqual(state.actions, [])
        self.assertEqual(result, original)
        self.assertNotIn("orchestration", result)


if __name__ == "__main__":
    unittest.main()
