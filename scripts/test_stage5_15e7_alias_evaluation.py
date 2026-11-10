"""Stage 5.15E.7: reviewed alias and replay tests."""

import copy
import json
import unittest
from pathlib import Path

from agent.semantic_alias_evaluation import (
    evaluate_with_aliases,
)

ROOT = Path(__file__).resolve().parents[1]
BENCHMARK = ROOT / "reports/stage5_15a_semantic_benchmark.json"
LIVE = ROOT / "reports/stage5_15e6_s03_live.json"


class SemanticAliasTests(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        benchmark = json.loads(
            BENCHMARK.read_text(encoding="utf-8-sig")
        )

        cls.reference = next(
            case for case in benchmark["cases"]
            if case["id"] == "S03"
        )

        cls.live = json.loads(
            LIVE.read_text(encoding="utf-8-sig")
        )

        if cls.live["outcome"] != "ACCEPTED":
            raise AssertionError("S03 live candidate was not accepted")

    def test_exact_mismatch_preserved(self):
        result = evaluate_with_aliases(
            self.live["candidate"], self.reference
        )
        self.assertFalse(result["exact"]["obligations_match"])

    def test_reviewed_alias_matches(self):
        result = evaluate_with_aliases(
            self.live["candidate"], self.reference
        )
        self.assertTrue(result["normalized_obligations_match"])
        self.assertTrue(result["handling_match"])
        self.assertTrue(result["period_match"])

    def test_alias_usage_is_auditable(self):
        result = evaluate_with_aliases(
            self.live["candidate"], self.reference
        )
        self.assertEqual(
            result["aliases_used"],
            [{
                "original": "discount_codes_filter",
                "reference": "discount_code_population",
            }],
        )

    def test_raw_candidate_unchanged(self):
        candidate = copy.deepcopy(self.live["candidate"])
        original = copy.deepcopy(candidate)

        evaluate_with_aliases(candidate, self.reference)

        self.assertEqual(candidate, original)

    def test_unknown_code_is_not_renamed(self):
        candidate = copy.deepcopy(self.live["candidate"])

        for item in candidate["obligations"]:
            if item["code"] == "discount_codes_filter":
                item["code"] = "unrelated_unknown_filter"

        result = evaluate_with_aliases(
            candidate, self.reference
        )

        self.assertFalse(result["normalized_obligations_match"])
        self.assertIn(
            "discount_code_population",
            result["normalized_missing"],
        )
        self.assertEqual(result["aliases_used"], [])

    def test_alias_collision_rejected(self):
        candidate = copy.deepcopy(self.live["candidate"])

        candidate["obligations"].append({
            "code": "discount_code_population",
            "capability_state": "UNVERIFIED_CAPABILITY",
        })

        with self.assertRaises(ValueError):
            evaluate_with_aliases(candidate, self.reference)

    def test_alias_does_not_upgrade_capability(self):
        result = evaluate_with_aliases(
            self.live["candidate"], self.reference
        )

        original_states = {
            item["code"]: item["capability_state"]
            for item in self.live["candidate"]["obligations"]
        }

        self.assertEqual(
            original_states["discount_codes_filter"],
            "UNVERIFIED_CAPABILITY",
        )
        self.assertFalse(result["execution_authorized"])
        self.assertFalse(result["completion_eligible"])
        self.assertEqual(
            result["evidence_state"], "NOT_ASSESSED"
        )


if __name__ == "__main__":
    unittest.main(verbosity=2)
