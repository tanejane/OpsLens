"""Stage 5.13L: feature-gated stop policy tests."""

import copy
import json
import unittest
from pathlib import Path
from unittest.mock import patch

from agent.coverage_stop_gate import apply_gate, REGISTRY
from scripts.phase5_3b_incident_eval import PROBE_BY_ID

ROOT = Path(__file__).resolve().parents[1]
SNAPSHOT = ROOT / "reports/stage5_12w_request_level_responses.json"


class CoverageGateTests(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.responses = json.loads(
            SNAPSHOT.read_text(encoding="utf-8-sig")
        )["responses"]

    def question(self, key):
        return PROBE_BY_ID[key].prompt

    def test_two_question_fingerprints_registered(self):
        self.assertEqual(len(REGISTRY), 2)

    def test_inc003_downgraded(self):
        result = apply_gate(
            self.question("INC_003"),
            self.responses["INC_003"],
        )
        self.assertEqual(
            result["orchestration"]["stop_reason"],
            "QUESTION_PARTIALLY_ADDRESSED",
        )
        self.assertEqual(
            result["orchestration"]["original_stop_reason"],
            "QUESTION_ADDRESSED",
        )
        self.assertEqual(
            result["coverage_assessment"]["policy"]
            ["coverage"]["requirements_satisfied"],
            2,
        )

    def test_inc004_preserved(self):
        result = apply_gate(
            self.question("INC_004"),
            self.responses["INC_004"],
        )
        self.assertEqual(
            result["orchestration"]["stop_reason"],
            "QUESTION_ADDRESSED",
        )
        self.assertTrue(
            result["coverage_assessment"]["policy"]
            ["may_claim_complete"]
        )

    def test_original_response_not_modified(self):
        response = copy.deepcopy(self.responses["INC_003"])
        original = copy.deepcopy(response)
        apply_gate(self.question("INC_003"), response)
        self.assertEqual(response, original)

    def test_unregistered_question_unchanged(self):
        response = self.responses["INC_003"]
        result = apply_gate(
            "What was the refund rate in January 2018?",
            response,
        )
        self.assertIs(result, response)

    def test_altered_question_unchanged(self):
        response = self.responses["INC_003"]
        result = apply_gate(
            self.question("INC_003") + " ",
            response,
        )
        self.assertIs(result, response)

    def test_existing_failure_preserved(self):
        response = copy.deepcopy(self.responses["INC_003"])
        response["orchestration"]["stop_reason"] = "TIME_BUDGET"
        result = apply_gate(self.question("INC_003"), response)
        self.assertIs(result, response)

    def test_wrong_route_not_modified(self):
        response = copy.deepcopy(self.responses["INC_003"])
        response["route"] = "investigation"
        result = apply_gate(self.question("INC_003"), response)
        self.assertIs(result, response)

    def test_no_tool_trace_mutation(self):
        response = copy.deepcopy(self.responses["INC_003"])
        original_trace = copy.deepcopy(
            response.get("execution_trace")
        )
        result = apply_gate(self.question("INC_003"), response)
        self.assertEqual(
            result.get("execution_trace"),
            original_trace,
        )
        self.assertEqual(
            result.get("validated_evidence"),
            response.get("validated_evidence"),
        )

    def test_missing_proof_prevents_completion(self):
        response = copy.deepcopy(self.responses["INC_004"])
        response["validated_evidence"] = []
        result = apply_gate(self.question("INC_004"), response)
        self.assertEqual(
            result["orchestration"]["stop_reason"],
            "QUESTION_NOT_DEMONSTRATED",
        )

    def test_policy_exception_fails_closed(self):
        response = copy.deepcopy(self.responses["INC_004"])
        with patch(
            "agent.coverage_stop_gate.recommend",
            side_effect=RuntimeError("test failure"),
        ):
            result = apply_gate(
                self.question("INC_004"),
                response,
            )
        self.assertEqual(
            result["orchestration"]["stop_reason"],
            "COVERAGE_EVALUATION_FAILED",
        )
        self.assertEqual(
            result["coverage_assessment"]["error_type"],
            "RuntimeError",
        )


if __name__ == "__main__":
    unittest.main(verbosity=2)
