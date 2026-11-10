
"""H.33 synthetic semantic assessment regression tests."""

import unittest
from agent.refund_semantic_v2 import assess


def action(detail=False, start="2018-01-01", end="2018-02-01"):
    return {
        "kind": "refund_concentration",
        "start": start,
        "end": end,
        "detail": detail,
    }


class RefundSemanticV2Tests(unittest.TestCase):

    def check(self, question, metric, selected, expected):
        result = assess(question, selected, metric)

        self.assertEqual(
            result["status"] == "METRIC_PERIOD_ACTION_MATCH",
            expected,
            result,
        )
        self.assertIs(result["execution_authorized"], False)
        self.assertIs(result["completion_authorized"], False)
        self.assertIs(
            result["source_provenance_authenticated"], False
        )
        self.assertEqual(
            result["evidence_state"], "NOT_ASSESSED"
        )

    def test_refund_rate(self):
        self.check(
            "What was the refund rate in January 2018?",
            "refund_rate", action(), True,
        )

    def test_refund_rate_paraphrase(self):
        self.check(
            "Give me the January 2018 refund rate.",
            "refund_rate", action(), True,
        )

    def test_return_rate(self):
        self.check(
            "What was the return rate in January 2018?",
            "return_rate", action(), True,
        )

    def test_refunded_order_count(self):
        self.check(
            "How many orders were refunded in January 2018?",
            "refunded_order_count", action(), True,
        )

    def test_returned_order_count(self):
        self.check(
            "How many orders had recorded returns in January 2018?",
            "returned_order_count", action(), True,
        )

    def test_refund_amount(self):
        self.check(
            "What was the refund amount in January 2018?",
            "refund_amount", action(), True,
        )

    def test_seller_refund_amount_ranking(self):
        self.check(
            "List the sellers with the highest refund amounts in January 2018.",
            "seller_refund_ranking", action(detail=True), True,
        )

    def test_wrong_metric(self):
        self.check(
            "What was the refund rate in January 2018?",
            "return_rate", action(), False,
        )

    def test_wrong_month(self):
        self.check(
            "What was the refund rate in January 2018?",
            "refund_rate",
            action(start="2018-02-01", end="2018-03-01"),
            False,
        )

    def test_wrong_year(self):
        self.check(
            "What was the refund rate in January 2018?",
            "refund_rate",
            action(start="2019-01-01", end="2019-02-01"),
            False,
        )

    def test_seller_detail_missing(self):
        self.check(
            "List the sellers with the highest refund amounts in January 2018.",
            "seller_refund_ranking",
            action(detail=False),
            False,
        )

    def test_seller_return_count_not_equated(self):
        self.check(
            "Which sellers had the most returns in January 2018?",
            "seller_refund_ranking",
            action(detail=True),
            False,
        )

    def test_filtered_population_rejected(self):
        self.check(
            "What was the refund rate in January 2018 for VIPs?",
            "refund_rate", action(), False,
        )

    def test_two_periods_rejected(self):
        self.check(
            "What was the refund rate in January 2018 and February 2018?",
            "refund_rate", action(), False,
        )

    def test_extra_action_field_rejected(self):
        selected = action()
        selected["payment_method"] = "visa"
        self.check(
            "What was the refund rate in January 2018?",
            "refund_rate", selected, False,
        )

    def test_december_boundary(self):
        self.check(
            "What was the refund rate in December 2018?",
            "refund_rate",
            action(start="2018-12-01", end="2019-01-01"),
            True,
        )

    def test_boolean_detail_rejected(self):
        selected = action()
        selected["detail"] = 0
        self.check(
            "What was the refund rate in January 2018?",
            "refund_rate", selected, False,
        )

    def test_missing_year_rejected(self):
        self.check(
            "What was the refund rate in January?",
            "refund_rate", action(), False,
        )


if __name__ == "__main__":
    unittest.main(verbosity=2)
