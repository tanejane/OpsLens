"""Stage 5.14G.1 association regression tests."""

import unittest

from agent.requirement_extractor import extract


class AssociationScopeTests(unittest.TestCase):

    def test_u10_abstains(self):
        result = extract(
            "Show January 2018 refund associations, "
            "not causal effects."
        )
        self.assertEqual(result["status"], "ABSTAIN")
        self.assertFalse(result["execution_authorized"])

    def test_regular_refund_measurement_preserved(self):
        result = extract(
            "What was the refund rate in January 2018?"
        )
        self.assertEqual(result["status"], "EXTRACTED")
        self.assertEqual(
            result["requirements"], ["monthly_returns"]
        )

    def test_explicit_seller_association_preserved(self):
        result = extract(
            "Which sellers were associated with returns "
            "in January 2018, not responsible for them?"
        )
        self.assertEqual(result["status"], "EXTRACTED")
        self.assertEqual(
            result["requirements"],
            ["monthly_returns", "refund_sellers"],
        )

    def test_delivery_noncausal_regression(self):
        result = extract(
            "Which sellers were associated with August 2018 "
            "delays, not responsible for them?"
        )
        self.assertEqual(result["status"], "EXTRACTED")

    def test_mixed_causal_question_still_abstains(self):
        result = extract(
            "Which sellers were not responsible for August "
            "2018 delays, and which sellers caused them?"
        )
        self.assertEqual(result["status"], "ABSTAIN")


if __name__ == "__main__":
    unittest.main(verbosity=2)
