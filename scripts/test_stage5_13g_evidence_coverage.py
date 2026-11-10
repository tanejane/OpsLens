"""Stage 5.13G: reusable evidence coverage regression."""

import copy
import json
import unittest
from pathlib import Path

from agent.evidence_coverage import evaluate, verify

ROOT = Path(__file__).resolve().parents[1]

SOURCE = (
    ROOT / "reports/stage5_12w_request_level_responses.json"
)


class EvidenceCoverageTests(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.responses = json.loads(
            SOURCE.read_text(encoding="utf-8-sig")
        )["responses"]

    def test_inc003_partial_coverage(self):
        result = evaluate(
            self.responses["INC_003"],
            ("2018-01-01", "2018-02-01"),
            {
                "monthly_returns": "monthly_returns",
                "seller_concentration": "refund_sellers",
                "product_concentration": None,
                "spike_comparison": None,
            },
        )

        self.assertEqual(result["decision"], "PARTIAL_EVIDENCE")
        self.assertEqual(result["requirements_satisfied"], 2)
        self.assertFalse(result["evaluation_complete"])

        self.assertEqual(
            [x["state"] for x in result["requirements"]],
            [
                "SATISFIED",
                "SATISFIED",
                "NOT_EVALUATED",
                "NOT_EVALUATED",
            ],
        )

    def test_inc004_complete_descriptive(self):
        result = evaluate(
            self.responses["INC_004"],
            ("2018-08-01", "2018-09-01"),
            {
                "delivery_rate": "late_delivery",
                "seller_concentration": "delivery_sellers",
            },
        )

        self.assertEqual(
            result["decision"],
            "COMPLETE_DESCRIPTIVE",
        )
        self.assertEqual(result["requirements_satisfied"], 2)
        self.assertTrue(result["evaluation_complete"])
        self.assertFalse(result["causal_mechanism_verified"])

        for item in result["requirements"]:
            self.assertIsNotNone(item["proof"]["retained_ref"])

    def test_tampered_evidence_rejected(self):
        result = copy.deepcopy(self.responses["INC_004"])
        result["seller_analysis"]["sellers"] = []

        proof = verify(
            result,
            "delivery_sellers",
            ("2018-08-01", "2018-09-01"),
        )

        self.assertIsNone(proof)

    def test_wrong_producer_rejected(self):
        result = copy.deepcopy(self.responses["INC_003"])
        archive = result["validated_evidence"]

        for entry in archive:
            if entry.get("producer") == (
                "agent.refund_concentration.validate_detail"
            ):
                entry["producer"] = "unapproved.validator"

        proof = verify(
            result,
            "refund_sellers",
            ("2018-01-01", "2018-02-01"),
        )

        self.assertIsNone(proof)

    def test_wrong_period_rejected(self):
        proof = verify(
            self.responses["INC_004"],
            "delivery_sellers",
            ("2018-07-01", "2018-08-01"),
        )

        self.assertIsNone(proof)

    def test_duplicate_proof_rejected(self):
        result = copy.deepcopy(self.responses["INC_004"])

        matching = next(
            entry for entry in result["validated_evidence"]
            if entry.get("producer")
            == "agent.seller_concentration.validate"
        )

        result["validated_evidence"].append(
            copy.deepcopy(matching)
        )

        proof = verify(
            result,
            "delivery_sellers",
            ("2018-08-01", "2018-09-01"),
        )

        self.assertIsNone(proof)

    def test_unknown_adapter_not_satisfied(self):
        result = evaluate(
            self.responses["INC_004"],
            ("2018-08-01", "2018-09-01"),
            {"unknown_requirement": "unregistered_adapter"},
        )

        self.assertEqual(result["decision"], "NOT_DEMONSTRATED")
        self.assertFalse(result["evaluation_complete"])
        self.assertEqual(
            result["requirements"][0]["state"],
            "NOT_EVALUATED",
        )

    def test_nonexecutable_result_not_accepted(self):
        result = copy.deepcopy(self.responses["INC_004"])
        result["executable"] = False

        assessed = evaluate(
            result,
            ("2018-08-01", "2018-09-01"),
            {"delivery_rate": "late_delivery"},
        )

        self.assertEqual(
            assessed["requirements"][0]["state"],
            "UNVERIFIED",
        )


if __name__ == "__main__":
    unittest.main(verbosity=2)
