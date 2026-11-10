
import copy
import unittest

from agent.structured_semantic_intent import (
    compare_intents,
    validate_intent,
)


def f06():
    return {
        "contract": "opslens.structured-intent.v1",
        "handling": "UNSUPPORTED_SCOPE",
        "metric": "refund_rate",
        "period": "2018-06",
        "operations": [
            {
                "kind": "FILTER",
                "field": "order_value_myr",
                "operator": "gt",
                "value": 200,
            },
            {
                "kind": "FILTER",
                "field": "payment_method",
                "operator": "eq",
                "value": "credit_card",
            },
        ],
        "clarifications": [],
        "execution_authorized": False,
        "completion_eligible": False,
        "evidence_state": "NOT_ASSESSED",
    }


def f08():
    result = f06()
    result["metric"] = "refund_rate"
    result["handling"] = "CLARIFICATION_REQUIRED"
    result["period"] = None
    result["operations"] = []
    result["clarifications"] = [
        "Which holiday period and year do you mean?"
    ]
    return result


class StructuredIntentTests(unittest.TestCase):

    def test_valid_f06(self):
        validate_intent(f06())

    def test_valid_f08(self):
        validate_intent(f08())

    def test_grouping_cannot_replace_credit_card_filter(self):
        candidate = f06()
        candidate["operations"][1] = {
            "kind": "GROUPING",
            "field": "payment_method",
        }
        result = compare_intents(candidate, f06())
        self.assertFalse(result["operations_match"])
        self.assertEqual(len(result["missing_operations"]), 1)

    def test_wrong_threshold_detected(self):
        candidate = f06()
        candidate["operations"][0]["value"] = 100
        result = compare_intents(candidate, f06())
        self.assertFalse(result["operations_match"])

    def test_missing_clarification_rejected(self):
        candidate = f08()
        candidate["clarifications"] = []
        with self.assertRaises(ValueError):
            validate_intent(candidate)

    def test_false_authority_rejected(self):
        candidate = copy.deepcopy(f06())
        candidate["execution_authorized"] = True
        with self.assertRaises(ValueError):
            validate_intent(candidate)


if __name__ == "__main__":
    unittest.main(verbosity=2)
