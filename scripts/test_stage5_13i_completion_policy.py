"""Stage 5.13I: advisory completion policy regression."""

import copy
import json
import unittest
from pathlib import Path

from agent.completion_policy import recommend

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "reports/stage5_12w_request_level_responses.json"

SPECS = {
    "INC_003": {
        "period": ("2018-01-01", "2018-02-01"),
        "requirements": {
            "monthly_returns": "monthly_returns",
            "seller_concentration": "refund_sellers",
            "product_concentration": None,
            "spike_comparison": None,
        },
    },
    "INC_004": {
        "period": ("2018-08-01", "2018-09-01"),
        "requirements": {
            "late_delivery": "late_delivery",
            "seller_concentration": "delivery_sellers",
        },
    },
}


class CompletionPolicyTests(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.responses = json.loads(
            SOURCE.read_text(encoding="utf-8-sig")
        )["responses"]

    def test_inc003_partial_not_complete(self):
        result = recommend(
            self.responses["INC_003"],
            SPECS["INC_003"],
        )
        self.assertEqual(
            result["decision"],
            "QUESTION_PARTIALLY_ADDRESSED",
        )
        self.assertFalse(result["may_claim_complete"])
        self.assertFalse(
            result["coverage"]["evaluation_complete"]
        )

    def test_inc004_complete_descriptive(self):
        result = recommend(
            self.responses["INC_004"],
            SPECS["INC_004"],
        )
        self.assertEqual(
            result["decision"],
            "QUESTION_ADDRESSED",
        )
        self.assertTrue(result["may_claim_complete"])
        self.assertFalse(
            result["coverage"]["causal_mechanism_verified"]
        )

    def test_missing_evidence_downgrades_completion(self):
        response = copy.deepcopy(self.responses["INC_004"])
        response["seller_analysis"]["sellers"] = []

        result = recommend(response, SPECS["INC_004"])

        self.assertEqual(
            result["decision"],
            "QUESTION_PARTIALLY_ADDRESSED",
        )
        self.assertFalse(result["may_claim_complete"])

    def test_all_proofs_missing(self):
        response = copy.deepcopy(self.responses["INC_004"])
        response["validated_evidence"] = []

        result = recommend(response, SPECS["INC_004"])

        self.assertEqual(
            result["decision"],
            "QUESTION_NOT_DEMONSTRATED",
        )
        self.assertFalse(result["may_claim_complete"])

    def test_nonexecutable_not_complete(self):
        response = copy.deepcopy(self.responses["INC_004"])
        response["executable"] = False

        result = recommend(response, SPECS["INC_004"])

        self.assertEqual(
            result["decision"],
            "QUESTION_NOT_DEMONSTRATED",
        )

    def test_unknown_specification_not_assessed(self):
        result = recommend(
            self.responses["INC_004"],
            None,
        )

        self.assertEqual(
            result["decision"],
            "COVERAGE_NOT_ASSESSED",
        )
        self.assertFalse(result["may_claim_complete"])

    def test_no_mutation(self):
        response = copy.deepcopy(self.responses["INC_003"])
        original = copy.deepcopy(response)

        recommend(response, SPECS["INC_003"])

        self.assertEqual(response, original)
        self.assertEqual(
            response["orchestration"]["stop_reason"],
            "QUESTION_ADDRESSED",
        )

    def test_malformed_specification_rejected(self):
        with self.assertRaises(ValueError):
            recommend(
                self.responses["INC_004"],
                {"requirements": {}},
            )


if __name__ == "__main__":
    unittest.main(verbosity=2)
