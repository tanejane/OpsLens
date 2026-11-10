
import copy
import json
import unittest

from agent.structured_gemini_proposer import (
    StructuredGeminiProposer,
    StructuredGenerationError,
    SYSTEM_INSTRUCTION,
)
from agent.structured_semantic_intent import (
    compare_intents,
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


class FakeResponse:
    def __init__(self, text):
        self.text = text


class FakeModels:
    def __init__(self, text=None, error=None):
        self.text = text
        self.error = error
        self.calls = []

    def generate_content(self, **kwargs):
        self.calls.append(kwargs)
        if self.error:
            raise self.error
        return FakeResponse(self.text)


class FakeClient:
    def __init__(self, text=None, error=None):
        self.models = FakeModels(text, error)


def proposer(payload):
    client = FakeClient(json.dumps(payload))
    return StructuredGeminiProposer(client, "fake-test-model"), client


class StructuredProposerTests(unittest.TestCase):

    def test_valid_structured_proposal(self):
        adapter, client = proposer(f06())
        result = adapter.propose("June refunds above RM200 paid by card")
        self.assertEqual(result, f06())
        self.assertEqual(len(client.models.calls), 1)
        config = client.models.calls[0]["config"]
        self.assertEqual(config.response_mime_type, "application/json")
        self.assertEqual(config.temperature, 0)

    def test_false_execution_authority_rejected(self):
        payload = f06()
        payload["execution_authorized"] = True
        adapter, _ = proposer(payload)
        with self.assertRaises(StructuredGenerationError):
            adapter.propose("Refunds")

    def test_missing_clarification_rejected(self):
        payload = f06()
        payload.update(
            handling="CLARIFICATION_REQUIRED",
            period=None,
            operations=[],
            clarifications=[],
        )
        adapter, _ = proposer(payload)
        with self.assertRaises(StructuredGenerationError):
            adapter.propose("Holiday refunds")

    def test_grouping_is_not_equivalent_to_filter(self):
        payload = f06()
        payload["operations"][1] = {
            "kind": "GROUPING",
            "field": "payment_method",
        }
        adapter, _ = proposer(payload)
        result = adapter.propose("Refunds above RM200 by credit card")
        comparison = compare_intents(result, f06())
        self.assertFalse(comparison["operations_match"])

    def test_duplicate_json_keys_rejected(self):
        raw = json.dumps(f06())
        raw = raw.replace(
            '"execution_authorized": false',
            '"execution_authorized": false, '
            '"execution_authorized": false',
        )
        client = FakeClient(raw)
        adapter = StructuredGeminiProposer(client, "fake-test-model")
        with self.assertRaises(StructuredGenerationError):
            adapter.propose("Refunds")

    def test_provider_failure_has_no_retry(self):
        client = FakeClient(error=RuntimeError("simulated outage"))
        adapter = StructuredGeminiProposer(client, "fake-test-model")
        with self.assertRaises(StructuredGenerationError):
            adapter.propose("Refunds")
        self.assertEqual(len(client.models.calls), 1)

    def test_prompt_requires_operation_distinction(self):
        self.assertIn("Never replace a filter with a grouping", SYSTEM_INSTRUCTION)
        self.assertIn("CLARIFICATION_REQUIRED", SYSTEM_INSTRUCTION)
        self.assertIn("execution_authorized: false", SYSTEM_INSTRUCTION)


if __name__ == "__main__":
    unittest.main(verbosity=2)
