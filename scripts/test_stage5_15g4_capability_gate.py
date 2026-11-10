
import copy
import json
import unittest
from pathlib import Path

from agent.structured_capability_gate import assess_capability

ROOT = Path(__file__).resolve().parents[1]
REPORT = ROOT / "reports/stage5_15g3_structured_live.json"


class CapabilityGateTests(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        data = json.loads(
            REPORT.read_text(encoding="utf-8-sig")
        )
        cls.candidates = {
            r["id"]: r["candidate"]
            for r in data["records"]
            if r["outcome"] == "ACCEPTED"
        }

        if set(cls.candidates) != {"F06", "F08"}:
            raise AssertionError(
                "Expected accepted F06 and F08 live records"
            )

    def test_f06_unverified_support_claim_detected(self):
        result = assess_capability(self.candidates["F06"])
        self.assertEqual(
            result["decision"], "CAPABILITY_NOT_VERIFIED"
        )
        self.assertTrue(result["support_claim_unverified"])

    def test_f08_requires_clarification(self):
        result = assess_capability(self.candidates["F08"])
        self.assertEqual(
            result["decision"], "CLARIFICATION_REQUIRED"
        )

    def test_no_execution_or_completion(self):
        for candidate in self.candidates.values():
            result = assess_capability(candidate)
            self.assertFalse(result["execution_authorized"])
            self.assertFalse(result["completion_eligible"])
            self.assertEqual(
                result["evidence_state"], "NOT_ASSESSED"
            )

    def test_does_not_modify_model_candidate(self):
        candidate = copy.deepcopy(self.candidates["F06"])
        before = copy.deepcopy(candidate)
        assess_capability(candidate)
        self.assertEqual(candidate, before)

    def test_supported_claim_without_operations_still_unverified(self):
        candidate = copy.deepcopy(self.candidates["F06"])
        candidate["operations"] = []
        result = assess_capability(candidate)
        self.assertEqual(
            result["decision"], "CAPABILITY_NOT_VERIFIED"
        )

    def test_invalid_authority_rejected(self):
        candidate = copy.deepcopy(self.candidates["F06"])
        candidate["execution_authorized"] = True
        with self.assertRaises(ValueError):
            assess_capability(candidate)


if __name__ == "__main__":
    unittest.main(verbosity=2)
