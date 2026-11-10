
"""H.31 deterministic binding tests; no runtime integration."""
import unittest

from agent.refund_metric_binding import assess

def action(detail=False):
    return {
        "kind": "refund_concentration",
        "start": "2018-01-01",
        "end": "2018-02-01",
        "detail": detail,
    }


class MetricBindingTests(unittest.TestCase):

    def check(self, question, metric, expected, selected=None):
        result = assess(
            question,
            metric,
            action() if selected is None else selected,
        )

        self.assertEqual(
            result["status"] == "METRIC_AND_OPERATION_BOUND",
            expected,
            result,
        )

        self.assertIs(result["execution_authorized"], False)
        self.assertIs(result["completion_authorized"], False)
        self.assertIs(
            result["source_provenance_authenticated"], False
        )

        return result

    def test_exact_refund_rate(self):
        self.check(
            "What was the refund rate in January 2018?",
            "refund_rate", True,
        )

    def test_refund_rate_paraphrase(self):
        self.check(
            "Give me the January 2018 refund rate.",
            "refund_rate", True,
        )

    def test_return_rate(self):
        self.check(
            "What was the return rate in January 2018?",
            "return_rate", True,
        )

    def test_refunded_order_count(self):
        self.check(
            "How many orders were refunded in January 2018?",
            "refunded_order_count", True,
        )

    def test_returned_order_count(self):
        self.check(
            "How many orders had recorded returns in January 2018?",
            "returned_order_count", True,
        )

    def test_refund_amount(self):
        self.check(
            "What was the refund amount in January 2018?",
            "refund_amount", True,
        )

    def test_seller_refund_amount_ranking(self):
        self.check(
            "List the sellers with the highest refund amounts in January 2018.",
            "seller_refund_ranking", True,
            action(detail=True),
        )

    def test_wrong_refund_vs_return_rate(self):
        self.check(
            "What was the refund rate in January 2018?",
            "return_rate", False,
        )

    def test_seller_returns_not_refund_amount_ranking(self):
        self.check(
            "Which sellers had the most returns in January 2018?",
            "seller_refund_ranking", False,
            action(detail=True),
        )

    def test_seller_ranking_not_overall_amount(self):
        self.check(
            "List the sellers with the highest refund amounts in January 2018.",
            "refund_amount", False,
            action(detail=True),
        )

    def test_seller_detail_mismatch(self):
        self.check(
            "List the sellers with the highest refund amounts in January 2018.",
            "seller_refund_ranking", False,
            action(detail=False),
        )

    def test_unsupported_vip_population(self):
        self.check(
            "What was the January 2018 refund rate for VIPs?",
            "refund_rate", False,
        )

    def test_unsupported_payment_filter(self):
        self.check(
            "What was the refund rate in January 2018 for Visa payments?",
            "refund_rate", False,
        )

    def test_two_periods_not_bound(self):
        self.check(
            "What was the refund rate in January 2018 and February 2018?",
            "refund_rate", False,
        )

    def test_unrecognized_question_not_bound(self):
        self.check(
            "Can you analyse refunds?",
            "refund_rate", False,
        )

    def test_extra_action_field_not_bound(self):
        selected = action()
        selected["population"] = "VIP"
        self.check(
            "What was the refund rate in January 2018?",
            "refund_rate", False,
            selected,
        )


if __name__ == "__main__":
    unittest.main(verbosity=2)
