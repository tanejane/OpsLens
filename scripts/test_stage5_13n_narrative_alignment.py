"""Stage 5.13N narrative alignment regression."""

import copy
import json
import unittest
from pathlib import Path

from agent.coverage_stop_gate import apply_gate
from scripts.phase5_3b_incident_eval import PROBE_BY_ID

ROOT = Path(__file__).resolve().parents[1]
SNAPSHOT = ROOT / "reports/stage5_12w_request_level_responses.json"


class NarrativeAlignmentTests(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.responses = json.loads(
            SNAPSHOT.read_text(encoding="utf-8-sig")
        )["responses"]

    def run_gate(self, incident):
        response = copy.deepcopy(self.responses[incident])
        response["explanation"] = {
            "version": "opslens.explanation.v1",
            "sections": [
                {
                    "kind": "fact",
                    "text": "Existing validated finding",
                    "evidence_refs": ["/payload/evidence"],
                    "causal_claim": False,
                }
            ],
        }

        original = copy.deepcopy(response)

        result = apply_gate(
            PROBE_BY_ID[incident].prompt,
            response,
        )

        return result, original, response

    def test_inc003_unresolved_requirements_visible(self):
        result, _, _ = self.run_gate("INC_003")
        sections = result["explanation"]["sections"]
        text = sections[-1]["text"]

        self.assertIn(
            "product-level return concentration",
            text,
        )
        self.assertIn(
            "comparison against a suitable baseline",
            text,
        )
        self.assertIn("NOT_EVALUATED", text)

    def test_inc003_original_findings_preserved(self):
        result, original, _ = self.run_gate("INC_003")
        self.assertEqual(
            result["explanation"]["sections"][0],
            original["explanation"]["sections"][0],
        )
        self.assertEqual(
            result["validated_evidence"],
            original["validated_evidence"],
        )

    def test_inc003_coverage_stop_consistent(self):
        result, _, _ = self.run_gate("INC_003")
        self.assertEqual(
            result["orchestration"]["stop_reason"],
            "QUESTION_PARTIALLY_ADDRESSED",
        )
        self.assertFalse(
            result["explanation"]["sections"][-1]["causal_claim"]
        )

    def test_inc004_no_unnecessary_limitation(self):
        result, original, _ = self.run_gate("INC_004")
        self.assertEqual(
            result["orchestration"]["stop_reason"],
            "QUESTION_ADDRESSED",
        )
        self.assertEqual(
            result["explanation"]["sections"],
            original["explanation"]["sections"],
        )

    def test_original_response_unchanged(self):
        _, original, response = self.run_gate("INC_003")
        self.assertEqual(response, original)

    def test_unregistered_question_untouched(self):
        response = copy.deepcopy(self.responses["INC_003"])
        result = apply_gate(
            "What was the refund rate in January 2018?",
            response,
        )
        self.assertIs(result, response)


if __name__ == "__main__":
    unittest.main(verbosity=2)
