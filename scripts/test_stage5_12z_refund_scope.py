"""Stage 5.12Z: refund-routing scope validation."""

import unittest

from agent.refund_routing import contextual


class RefundScopeTests(unittest.TestCase):

    def test_inc012_rejected(self):
        question = (
            "In July 2018, refund rates were 10% among "
            "promotion-exposed orders and 4.64% otherwise. "
            "Did promotions cause refunds? Check order-value strata."
        )
        action, response, _ = contextual(question, {}, {})
        self.assertIsNone(action)
        self.assertEqual(response["status"], "NOT_YET_SUPPORTED")
        self.assertIs(response["executable"], False)
        self.assertIs(response["approved_for_mcp"], False)
        self.assertIs(response["causal_claim"], False)

    def test_inc010_rejected(self):
        question = (
            "Investigate December 2017 fulfillment and refunds, "
            "but the final supplier invoice reconciliation and "
            "paid-media accrual are unavailable. "
            "What can you conclude?"
        )
        action, response, _ = contextual(question, {}, {})
        self.assertIsNone(action)
        self.assertEqual(response["status"], "NOT_YET_SUPPORTED")

    def test_ordinary_refund_measurement_preserved(self):
        action, immediate, _ = contextual(
            "What was the refund rate in July 2018?",
            {}, {},
        )
        self.assertIsNone(immediate)
        self.assertEqual(action["kind"], "refund_concentration")

    def test_seller_concentration_preserved(self):
        action, immediate, _ = contextual(
            "Which sellers had the most returns in January 2018?",
            {}, {},
        )
        self.assertIsNone(immediate)
        self.assertEqual(action["kind"], "refund_concentration")
        self.assertTrue(action["detail"])

    def test_unrelated_question_not_intercepted(self):
        self.assertIsNone(
            contextual("What was revenue in February 2018?", {}, {})
        )


if __name__ == "__main__":
    unittest.main(verbosity=2)
