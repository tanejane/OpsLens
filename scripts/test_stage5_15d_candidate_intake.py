"""Stage 5.15D: untrusted candidate intake verification."""

import copy
import json
import unittest

from agent.semantic_candidate_intake import accept_candidate
from agent.semantic_proposal import CONTRACT


def base():
    return {
        "contract": CONTRACT,
        "handling": "SUPPORTED_CANDIDATE",
        "period": "2018-06",
        "obligations": [
            {
                "code": "refund_rate",
                "capability_state": "KNOWN_LABEL",
            },
        ],
        "execution_authorized": False,
        "evidence_state": "NOT_ASSESSED",
        "completion_eligible": False,
    }


class CandidateIntakeTests(unittest.TestCase):

    def test_valid_supported_candidate(self):
        proposal = accept_candidate(json.dumps(base()))
        self.assertEqual(proposal["handling"], "SUPPORTED_CANDIDATE")

    def test_unknown_obligation_must_be_unverified(self):
        candidate = base()
        candidate["handling"] = "UNSUPPORTED_SCOPE"
        candidate["obligations"].append({
            "code": "discount_code_population",
            "capability_state": "UNVERIFIED_CAPABILITY",
        })

        accepted = accept_candidate(json.dumps(candidate))
        self.assertEqual(len(accepted["obligations"]), 2)

        candidate["obligations"][1][
            "capability_state"
        ] = "KNOWN_LABEL"

        with self.assertRaises(ValueError):
            accept_candidate(json.dumps(candidate))

    def test_rejects_execution_and_completion_claims(self):
        for field, invalid in (
            ("execution_authorized", True),
            ("completion_eligible", True),
            ("evidence_state", "VERIFIED"),
        ):
            with self.subTest(field=field):
                candidate = base()
                candidate[field] = invalid
                with self.assertRaises(ValueError):
                    accept_candidate(json.dumps(candidate))

    def test_rejects_duplicate_json_keys(self):
        raw = json.dumps(base())
        raw = raw.replace(
            '"execution_authorized": false',
            '"execution_authorized": false, '
            '"execution_authorized": false',
        )
        with self.assertRaises(ValueError):
            accept_candidate(raw)

    def test_rejects_oversized_candidates(self):
        with self.assertRaises(ValueError):
            accept_candidate(" " * 17000)

    def test_rejects_unknown_known_label(self):
        candidate = base()
        candidate["obligations"][0]["code"] = "invented_capability"
        with self.assertRaises(ValueError):
            accept_candidate(json.dumps(candidate))

    def test_rejected_cannot_hide_analysis_obligation(self):
        candidate = base()
        candidate["handling"] = "REJECTED"
        candidate["period"] = None
        candidate["obligations"] = [{
            "code": "reject_instruction_override",
            "capability_state": "KNOWN_LABEL",
        }]

        self.assertEqual(
            accept_candidate(json.dumps(candidate))["handling"],
            "REJECTED",
        )

        candidate["obligations"].append({
            "code": "refund_rate",
            "capability_state": "KNOWN_LABEL",
        })

        with self.assertRaises(ValueError):
            accept_candidate(json.dumps(candidate))

    def test_security_guidance_must_preserve_obligations(self):
        candidate = base()
        candidate["handling"] = "SECURITY_GUIDANCE"
        candidate["period"] = None
        candidate["obligations"] = [
            {"code": code, "capability_state": "KNOWN_LABEL"}
            for code in sorted({
                "untrusted_content_recognition",
                "protect_private_instructions",
                "reject_unapproved_write",
            })
        ]

        self.assertEqual(
            accept_candidate(json.dumps(candidate))["handling"],
            "SECURITY_GUIDANCE",
        )

        candidate["obligations"].pop()

        with self.assertRaises(ValueError):
            accept_candidate(json.dumps(candidate))

    def test_rejects_markdown_wrapped_json(self):
        raw = "```json\n" + json.dumps(base()) + "\n```"
        with self.assertRaises(ValueError):
            accept_candidate(raw)


if __name__ == "__main__":
    unittest.main(verbosity=2)
