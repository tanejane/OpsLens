
"""H.21 shadow contract tests; no production routing changes."""
import unittest

from agent.refund_semantic_contract import verify


def action(start="2018-01-01", end="2018-02-01", detail=False):
    return {
        "kind": "refund_concentration",
        "start": start,
        "end": end,
        "detail": detail,
    }


def prior(detail=True):
    return {
        "payload": {
            "route": "refund_concentration",
            "status": "MEASURED_WITH_LIMITATIONS",
            "executable": True,
            "causal_claim": False,
            "refund_intent": detail,
            "evidence": {
                "period": ["2018-01-01", "2018-02-01"],
            },
        }
    }


class RefundSemanticContractTests(unittest.TestCase):

    def check(self, question, selected, recognized, **kwargs):
        result = verify(question, selected, **kwargs)
        self.assertEqual(
            result["status"] != "NOT_VERIFIED", recognized
        )
        self.assertIs(result["execution_authorized"], False)
        self.assertEqual(result["evidence_state"], "NOT_ASSESSED")
        return result

    def test_supported_measurement(self):
        self.check(
            "What was the refund rate in January 2018?",
            action(), True
        )

    def test_seller_detail_required(self):
        question = (
            "Which sellers had the most returns in January 2018?"
        )
        self.check(question, action(detail=True), True)
        self.check(question, action(detail=False), False)

    def test_unnecessary_detail_not_silently_added(self):
        self.check(
            "What was the refund rate in January 2018?",
            action(detail=True), False
        )

    def test_period_mismatch(self):
        self.check(
            "What was the refund rate in January 2018?",
            action("2018-02-01", "2018-03-01"),
            False,
        )

    def test_extra_action_field(self):
        modified = action()
        modified["payment_method"] = "visa"
        self.check(
            "What was the refund rate in January 2018?",
            modified, False
        )

    def test_restricted_questions(self):
        questions = (
            "Show January 2018 refunds for Visa payments.",
            "Calculate January 2018 refund rates for new buyers.",
            "Show January 2018 refunds by membership level.",
            "Calculate January 2018 refund rates for coupon users.",
            "Show January 2018 refunds for website purchases.",
            "Calculate January 2018 refund rates above RM200.",
            "Find the refund rate for enterprise customers in January 2018.",
        )
        for question in questions:
            with self.subTest(question=question):
                self.check(question, action(), False)

    def test_untrusted_context_not_accepted(self):
        self.check(
            "Which sellers?", action(detail=True), False,
            prior=prior(), context_trusted=False
        )

    def test_contextual_seller_detail(self):
        self.check(
            "Which sellers?", action(detail=True), True,
            prior=prior(), context_trusted=True
        )
        self.check(
            "Which sellers?", action(detail=False), False,
            prior=prior(), context_trusted=True
        )

    def test_contextual_month(self):
        self.check(
            "What about February 2018?",
            action("2018-02-01", "2018-03-01"),
            True,
            prior=prior(False),
            context_trusted=True,
        )

    def test_pending_year(self):
        self.check(
            "2018", action(), True,
            pending={
                "capability": "refund_concentration",
                "question": "What was the refund rate in January?",
                "detail": False,
            },
            context_trusted=True,
        )

    def test_clarification_never_verified(self):
        self.check(
            "What was the refund rate in January?",
            action(), False,
            immediate={
                "status": "NEEDS_CLARIFICATION",
                "executable": False,
            },
        )

    def test_forged_looking_prior_not_authenticated(self):
        self.check(
            "Which sellers?", action(detail=True), False,
            prior=prior(),
            context_trusted=False,
        )


if __name__ == "__main__":
    unittest.main(verbosity=2)
