"""Stage 5.15E.10 vocabulary-instruction regression."""

import json
import unittest

from agent.semantic_gemini_proposer import (
    SYSTEM_INSTRUCTION,
    SemanticGeminiProposer,
    CandidateGenerationError,
)


class FakeResponse:
    def __init__(self, text):
        self.text = text


class FakeModels:
    def __init__(self, payload):
        self.payload = payload
        self.calls = []

    def generate_content(self, **kwargs):
        self.calls.append(kwargs)
        return FakeResponse(json.dumps(self.payload))


class FakeClient:
    def __init__(self, payload):
        self.models = FakeModels(payload)


def s04_candidate(handling, refund_code, payment_code, payment_state):
    return {
        "contract": "opslens.semantic-proposal.v1",
        "handling": handling,
        "period": "2018-06",
        "obligations": [
            {
                "code": refund_code,
                "capability_state": "KNOWN_LABEL",
            },
            {
                "code": payment_code,
                "capability_state": payment_state,
            },
        ],
        "execution_authorized": False,
        "evidence_state": "NOT_ASSESSED",
        "completion_eligible": False,
    }


class VocabularyGuidanceTests(unittest.TestCase):

    def test_prompt_names_exact_refund_and_grouping_obligations(self):
        for phrase in (
            "refund_measurement",
            "refund_rate",
            "payment_method_grouping",
            "UNVERIFIED_CAPABILITY",
            "UNSUPPORTED_SCOPE",
        ):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, SYSTEM_INSTRUCTION)

    def test_original_s04_pattern_still_rejected(self):
        payload = s04_candidate(
            "SUPPORTED_CANDIDATE",
            "refunds",
            "payment_method",
            "KNOWN_LABEL",
        )
        client = FakeClient(payload)
        proposer = SemanticGeminiProposer(
            client, "fake-test-model"
        )

        with self.assertRaises(CandidateGenerationError):
            proposer.propose(
                "Report June 2018 refunds grouped by payment method."
            )

        self.assertEqual(len(client.models.calls), 1)

    def test_coherent_s04_pattern_accepted(self):
        payload = s04_candidate(
            "UNSUPPORTED_SCOPE",
            "refund_measurement",
            "payment_method_grouping",
            "UNVERIFIED_CAPABILITY",
        )
        client = FakeClient(payload)
        proposer = SemanticGeminiProposer(
            client, "fake-test-model"
        )

        result = proposer.propose(
            "Report June 2018 refunds grouped by payment method."
        )

        self.assertEqual(
            result["handling"], "UNSUPPORTED_SCOPE"
        )
        self.assertEqual(
            [x["code"] for x in result["obligations"]],
            ["refund_measurement", "payment_method_grouping"],
        )
        self.assertFalse(result["execution_authorized"])
        self.assertFalse(result["completion_eligible"])

    def test_no_sql_or_authority_injected(self):
        self.assertIn(
            "Do not invent executable adapters",
            SYSTEM_INSTRUCTION,
        )
        self.assertIn(
            "Never include SQL, tool calls",
            SYSTEM_INSTRUCTION,
        )


if __name__ == "__main__":
    unittest.main(verbosity=2)
