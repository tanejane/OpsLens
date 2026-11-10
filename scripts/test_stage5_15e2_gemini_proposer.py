"""Stage 5.15E.2: fake-client Gemini proposer tests."""

import json
import unittest

from agent.semantic_gemini_proposer import (
    CandidateGenerationError,
    SemanticGeminiProposer,
)


def valid_candidate():
    return {
        "contract": "opslens.semantic-proposal.v1",
        "handling": "SUPPORTED_CANDIDATE",
        "period": "2018-06",
        "obligations": [{
            "code": "refund_rate",
            "capability_state": "KNOWN_LABEL",
        }],
        "execution_authorized": False,
        "evidence_state": "NOT_ASSESSED",
        "completion_eligible": False,
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

        if self.error is not None:
            raise self.error

        return FakeResponse(self.text)


class FakeClient:
    def __init__(self, text=None, error=None):
        self.models = FakeModels(text=text, error=error)


class GeminiProposerTests(unittest.TestCase):

    def test_valid_candidate(self):
        client = FakeClient(
            text=json.dumps(valid_candidate())
        )
        proposer = SemanticGeminiProposer(
            client, "fake-test-model"
        )

        result = proposer.propose(
            "What was the refund rate in June 2018?"
        )

        self.assertEqual(
            result["handling"], "SUPPORTED_CANDIDATE"
        )
        self.assertFalse(result["execution_authorized"])
        self.assertFalse(result["completion_eligible"])
        self.assertEqual(len(client.models.calls), 1)

    def test_sdk_request_configuration(self):
        client = FakeClient(
            text=json.dumps(valid_candidate())
        )
        proposer = SemanticGeminiProposer(
            client, "fake-test-model"
        )

        question = "What was the refund rate in June 2018?"
        proposer.propose(question)

        call = client.models.calls[0]

        self.assertEqual(call["model"], "fake-test-model")
        self.assertEqual(call["contents"], question)
        self.assertEqual(
            call["config"].response_mime_type,
            "application/json",
        )
        self.assertEqual(call["config"].temperature, 0)
        self.assertLessEqual(
            call["config"].max_output_tokens, 2048
        )

    def test_invalid_question_never_calls_model(self):
        client = FakeClient(
            text=json.dumps(valid_candidate())
        )
        proposer = SemanticGeminiProposer(
            client, "fake-test-model"
        )

        for question in ("", " ", "x" * 2001, None):
            with self.subTest(question_type=type(question)):
                with self.assertRaises(
                    CandidateGenerationError
                ):
                    proposer.propose(question)

        self.assertEqual(client.models.calls, [])

    def test_provider_failure_is_isolated(self):
        client = FakeClient(
            error=RuntimeError("simulated failure")
        )
        proposer = SemanticGeminiProposer(
            client, "fake-test-model"
        )

        with self.assertRaises(CandidateGenerationError):
            proposer.propose(
                "What was the refund rate in June 2018?"
            )

    def test_empty_model_response_rejected(self):
        for value in (None, "", " "):
            with self.subTest(value=value):
                client = FakeClient(text=value)
                proposer = SemanticGeminiProposer(
                    client, "fake-test-model"
                )

                with self.assertRaises(
                    CandidateGenerationError
                ):
                    proposer.propose(
                        "What was the refund rate in June 2018?"
                    )

    def test_malformed_json_rejected(self):
        client = FakeClient(text='{"handling": ')
        proposer = SemanticGeminiProposer(
            client, "fake-test-model"
        )

        with self.assertRaises(CandidateGenerationError):
            proposer.propose(
                "What was the refund rate in June 2018?"
            )

    def test_false_authorization_rejected(self):
        candidate = valid_candidate()
        candidate["execution_authorized"] = True

        client = FakeClient(text=json.dumps(candidate))
        proposer = SemanticGeminiProposer(
            client, "fake-test-model"
        )

        with self.assertRaises(CandidateGenerationError):
            proposer.propose(
                "What was the refund rate in June 2018?"
            )

    def test_unverified_capability_preserved(self):
        candidate = valid_candidate()
        candidate["handling"] = "UNSUPPORTED_SCOPE"
        candidate["obligations"].append({
            "code": "discount_code_population",
            "capability_state": "UNVERIFIED_CAPABILITY",
        })

        client = FakeClient(text=json.dumps(candidate))
        proposer = SemanticGeminiProposer(
            client, "fake-test-model"
        )

        result = proposer.propose(
            "What was the refund rate among discount-code "
            "users in June 2018?"
        )

        self.assertIn(
            "discount_code_population",
            [x["code"] for x in result["obligations"]],
        )

    def test_no_automatic_fallback(self):
        client = FakeClient(text="not JSON")
        proposer = SemanticGeminiProposer(
            client, "fake-test-model"
        )

        with self.assertRaises(CandidateGenerationError):
            proposer.propose(
                "What was the refund rate in June 2018?"
            )

        self.assertEqual(len(client.models.calls), 1)

    def test_explicit_model_required(self):
        client = FakeClient(
            text=json.dumps(valid_candidate())
        )
        with self.assertRaises(ValueError):
            SemanticGeminiProposer(client, "")


if __name__ == "__main__":
    unittest.main(verbosity=2)
