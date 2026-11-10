
"""H.39 action policy tests; pure routing, no executor."""
import unittest
from agent.refund_routing import contextual
from agent.refund_action_policy import evaluate


class RefundActionPolicyTests(unittest.TestCase):

    def check(self, question, expected):
        routed = contextual(question, {}, {})
        action = routed[0] if routed else None
        result = evaluate(question, action)

        self.assertEqual(result["decision"], expected, result)
        self.assertIs(result["execution_authorized"], False)
        self.assertIs(result["completion_authorized"], False)

    def test_regular_refund_rate(self):
        self.check(
            "What was the refund rate in January 2018?",
            "SEMANTIC_MATCH_SHADOW",
        )

    def test_refund_rate_paraphrase(self):
        self.check(
            "Give me the January 2018 refund rate.",
            "SEMANTIC_MATCH_SHADOW",
        )

    def test_seller_refund_amount_ranking(self):
        self.check(
            "List the sellers with the highest refund amounts in January 2018.",
            "SEMANTIC_MATCH_SHADOW",
        )

    def test_vip_filter(self):
        self.check(
            "What was the January 2018 refund rate for VIPs?",
            "NOT_VERIFIED",
        )

    def test_enterprise_filter(self):
        self.check(
            "Show refund rate for enterprise customers in January 2018.",
            "NOT_VERIFIED",
        )

    def test_returning_customers(self):
        self.check(
            "Give me the January 2018 refund rate for returning customers.",
            "NOT_VERIFIED",
        )

    def test_membership_filter(self):
        self.check(
            "Give me the January 2018 refund rate for members.",
            "NOT_VERIFIED",
        )

    def test_wrong_seller_ranking(self):
        self.check(
            "Which sellers had the most returns in January 2018?",
            "NOT_VERIFIED",
        )

    def test_unknown_question_without_refund_action(self):
        self.check(
            "What about February 2018 for VIPs?",
            "NO_REFUND_ACTION",
        )

    def test_contextual_action_requires_review(self):
        selected = {
            "kind": "refund_concentration",
            "start": "2018-02-01",
            "end": "2018-03-01",
            "detail": False,
        }
        result = evaluate("What about February 2018?", selected)
        self.assertEqual(result["decision"], "NOT_VERIFIED")
        self.assertIs(result["execution_authorized"], False)

    def test_action_period_mutation(self):
        selected = {
            "kind": "refund_concentration",
            "start": "2018-02-01",
            "end": "2018-03-01",
            "detail": False,
        }
        result = evaluate(
            "What was the refund rate in January 2018?",
            selected,
        )
        self.assertEqual(result["decision"], "NOT_VERIFIED")
        self.assertIs(result["execution_authorized"], False)

    def test_other_action_not_assessed(self):
        result = evaluate(
            "Calculate revenue in January 2018",
            {"kind": "finance"},
        )
        self.assertEqual(
            result["decision"], "OTHER_ACTION_NOT_ASSESSED"
        )
        self.assertIs(result["execution_authorized"], False)


if __name__ == "__main__":
    unittest.main(verbosity=2)
