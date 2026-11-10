
import unittest
from agent.refund_context_binding import assess

def action(month=1, year=2018, detail=False):
    from datetime import date
    end_year = year + (month == 12)
    end_month = month % 12 + 1
    return {
        "kind": "refund_concentration",
        "start": date(year, month, 1).isoformat(),
        "end": date(end_year, end_month, 1).isoformat(),
        "detail": detail,
    }

def prior(metric="refund_rate", question=None, recorded_metric=None):
    if question is None:
        question = (
            "What was the refund rate in January 2018?"
            if metric == "refund_rate"
            else "What was the return rate in January 2018?"
        )
    evidence = {"period": ["2018-01-01", "2018-02-01"]}
    if recorded_metric is not None:
        evidence["metric_id"] = recorded_metric
    return {
        "question": question,
        "payload": {
            "route": "refund_concentration",
            "status": "MEASURED_WITH_LIMITATIONS",
            "executable": True,
            "causal_claim": False,
            "evidence": evidence,
        },
    }

class ContextBindingTests(unittest.TestCase):
    def check(self, question, selected, expected, **kwargs):
        result = assess(question, selected, **kwargs)
        self.assertEqual(result["status"], expected, result)
        self.assertIs(result["execution_authorized"], False)
        self.assertIs(result["completion_authorized"], False)
        self.assertIs(result["session_authenticated"], False)
        return result

    def test_pending_year(self):
        result = self.check(
            "2018", action(),
            "CONTEXT_SEMANTIC_MATCH_SHADOW",
            pending={
                "capability": "refund_concentration",
                "question": "What was the refund rate in January",
                "detail": False,
            },
        )
        self.assertEqual(result["requested_metric"], "refund_rate")

    def test_pending_wrong_year(self):
        self.check(
            "2018", action(year=2019), "NOT_VERIFIED",
            pending={
                "capability": "refund_concentration",
                "question": "What was the refund rate in January",
            },
        )

    def test_pending_without_context(self):
        self.check("2018", action(), "NOT_VERIFIED")

    def test_refund_month_followup(self):
        result = self.check(
            "What about February 2018?",
            action(month=2),
            "CONTEXT_SEMANTIC_MATCH_SHADOW",
            prior=prior("refund_rate"),
        )
        self.assertEqual(result["requested_metric"], "refund_rate")

    def test_return_rate_remains_return_rate(self):
        result = self.check(
            "What about February 2018?",
            action(month=2),
            "CONTEXT_SEMANTIC_MATCH_SHADOW",
            prior=prior("return_rate"),
        )
        self.assertEqual(result["requested_metric"], "return_rate")

    def test_missing_prior_question(self):
        record = prior()
        record["question"] = None
        self.check(
            "What about February 2018?",
            action(month=2), "NOT_VERIFIED",
            prior=record,
        )

    def test_wrong_month(self):
        self.check(
            "What about February 2018?",
            action(month=3), "NOT_VERIFIED",
            prior=prior(),
        )

    def test_previous_period_disagreement(self):
        record = prior()
        record["payload"]["evidence"]["period"] = [
            "2018-03-01", "2018-04-01"
        ]
        self.check(
            "What about February 2018?",
            action(month=2), "NOT_VERIFIED",
            prior=record,
        )

    def test_conflicting_recorded_metric(self):
        self.check(
            "What about February 2018?",
            action(month=2), "NOT_VERIFIED",
            prior=prior("return_rate", recorded_metric="refund_rate"),
        )

    def test_filtered_followup(self):
        self.check(
            "What about February 2018 for VIPs?",
            action(month=2), "NOT_VERIFIED",
            prior=prior(),
        )

    def test_seller_followup_not_inferred(self):
        self.check(
            "Which sellers?",
            action(detail=True), "NOT_VERIFIED",
            prior=prior(),
        )

    def test_prior_not_validated(self):
        record = prior()
        record["payload"]["executable"] = False
        self.check(
            "What about February 2018?",
            action(month=2), "NOT_VERIFIED",
            prior=record,
        )

if __name__ == "__main__":
    unittest.main(verbosity=2)
