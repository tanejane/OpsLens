"""Stage 5.15E.5: handling alignment regression tests."""

import json
import unittest

from agent.semantic_gemini_proposer import (
    CandidateGenerationError,
    SYSTEM_INSTRUCTION,
    SemanticGeminiProposer,
)


class FakeResponse:
    def __init__(self, text):
        self.text = text


class FakeModels:
    def __init__(self, response):
        self.response = response
        self.calls = 0

    def generate_content(self, **kwargs):
        self.calls += 1
        return FakeResponse(json.dumps(self.response))


class FakeClient:
    def __init__(self, response):
        self.models = FakeModels(response)


def candidate(handling):
    return {
        "contract": "opslens.semantic-proposal.v1",
        "handling": handling,
        "period": "2018-06",
        "obligations": [
            {
                "code": "refund_rate",
                "capability_state": "KNOWN_LABEL",
            },
            {
                "code": "discount_code_population",
                "capability_state": "UNVERIFIED_CAPABILITY",
            },
        ],
        "execution_authorized": False,
        "evidence_state": "NOT_ASSESSED",
        "completion_eligible": False,
    }


class HandlingAlignmentTests(unittest.TestCase):

    def test_prompt_explicitly_requires_consistency(self):
        self.assertIn(
            "CRITICAL HANDLING CONSISTENCY",
            SYSTEM_INSTRUCTION,
        )
        self.assertIn(
            "handling MUST NOT be SUPPORTED_CANDIDATE",
            SYSTEM_INSTRUCTION,
        )
        self.assertIn(
            "Never remove an unsupported obligation",
            SYSTEM_INSTRUCTION,
        )

    def test_unsupported_candidate_accepted(self):
        client = FakeClient(candidate("UNSUPPORTED_SCOPE"))
        proposer = SemanticGeminiProposer(
            client, "fake-test-model"
        )

        result = proposer.propose(
            "June 2018 refund rate among discount-code users"
        )

        self.assertEqual(
            result["handling"], "UNSUPPORTED_SCOPE"
        )
        self.assertEqual(
            {x["code"] for x in result["obligations"]},
            {"refund_rate", "discount_code_population"},
        )

    def test_contradictory_candidate_still_rejected(self):
        client = FakeClient(
            candidate("SUPPORTED_CANDIDATE")
        )
        proposer = SemanticGeminiProposer(
            client, "fake-test-model"
        )

        with self.assertRaises(CandidateGenerationError):
            proposer.propose(
                "June 2018 refund rate among discount-code users"
            )

        self.assertEqual(client.models.calls, 1)


if __name__ == "__main__":
    unittest.main(verbosity=2)
