
"""Regression tests for refund-router semantic scope preservation.

These tests are intentionally expected to reveal five existing
failures before a production router patch is applied.
"""

import unittest

from agent.refund_routing import contextual


CASES = {
    "H01": (
        "Calculate June 2018 refund rates.",
        True,
    ),
    "H02": (
        "Calculate June 2018 refund rates "
        "for orders above RM200.",
        False,
    ),
    "H03": (
        "Calculate June 2018 refund rates "
        "for purchases paid by credit card.",
        False,
    ),
    "H04": (
        "Calculate June 2018 refund rates "
        "for first-time buyers.",
        False,
    ),
    "H05": (
        "Show June 2018 refund counts "
        "by customer loyalty tier.",
        False,
    ),
    "H06": (
        "Calculate June 2018 refund rates "
        "for customers using discount codes.",
        False,
    ),
    "H07": (
        "Calculate June 2018 refund rates "
        "for orders over RM200 paid by credit card.",
        False,
    ),
    "H08": (
        "Calculate June 2018 refund rates "
        "for mobile-app purchases.",
        False,
    ),
}


def refund_route_selected(question):
    result = contextual(question, {}, {})

    if result is None:
        return False

    context, immediate, _ = result

    return (
        immediate is None
        and isinstance(context, dict)
        and context.get("kind") == "refund_concentration"
    )


class RefundScopeGuardTests(unittest.TestCase):

    def test_baseline_route_remains_available(self):
        question, expected = CASES["H01"]
        self.assertEqual(refund_route_selected(question), expected)

    def test_existing_amount_restriction_blocked(self):
        question, expected = CASES["H02"]
        self.assertEqual(refund_route_selected(question), expected)

    def test_existing_combined_restriction_blocked(self):
        question, expected = CASES["H07"]
        self.assertEqual(refund_route_selected(question), expected)

    def test_credit_card_filter_not_dropped(self):
        question, expected = CASES["H03"]
        self.assertEqual(refund_route_selected(question), expected)

    def test_first_time_buyer_filter_not_dropped(self):
        question, expected = CASES["H04"]
        self.assertEqual(refund_route_selected(question), expected)

    def test_loyalty_tier_grouping_not_dropped(self):
        question, expected = CASES["H05"]
        self.assertEqual(refund_route_selected(question), expected)

    def test_discount_code_filter_not_dropped(self):
        question, expected = CASES["H06"]
        self.assertEqual(refund_route_selected(question), expected)

    def test_mobile_app_filter_not_dropped(self):
        question, expected = CASES["H08"]
        self.assertEqual(refund_route_selected(question), expected)


if __name__ == "__main__":
    unittest.main(verbosity=2)
