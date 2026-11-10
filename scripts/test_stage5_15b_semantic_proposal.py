"""Stage 5.15B: proposal contract and semantic omission tests."""

import copy
import hashlib
import json
import unittest
from pathlib import Path

from agent.semantic_proposal import (
    CONTRACT,
    compare_to_reference,
    validate_proposal,
)

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "reports/stage5_15a_semantic_benchmark.json"

EXPECTED_DIGEST = (
    "bcde896a4b6a8884f0f4238540aa6df"
    "886c6f20907e52e634064905208364b60"
)

# These are fixture annotations, not independently generated predictions.
UNVERIFIED = {
    "discount_code_population",
    "payment_method_grouping",
    "order_value_threshold",
    "before_after_comparison",
    "destination_filter",
    "customer_satisfaction",
    "cross_domain_comparison",
    "seller_causal_identification",
}

REVIEW = {
    "year_clarification",
    "refund_investigation",
    "investigation_scope_clarification",
}


def fixture_from_reference(case):
    obligations = []
    for code in case["obligations"]:
        state = (
            "UNVERIFIED_CAPABILITY" if code in UNVERIFIED
            else "REVIEW_REQUIRED" if code in REVIEW
            else "KNOWN_LABEL"
        )
        obligations.append({
            "code": code,
            "capability_state": state,
        })

    return {
        "contract": CONTRACT,
        "handling": case["handling"],
        "period": case["period"],
        "obligations": obligations,
        "execution_authorized": False,
        "evidence_state": "NOT_ASSESSED",
        "completion_eligible": False,
    }


class SemanticProposalTests(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.data = json.loads(
            SOURCE.read_text(encoding="utf-8-sig")
        )
        canonical = json.dumps(
            cls.data["cases"],
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        )
        actual_digest = hashlib.sha256(
            canonical.encode("utf-8")
        ).hexdigest()

        if actual_digest != EXPECTED_DIGEST:
            raise AssertionError(
                "Frozen Stage 5.15A benchmark fingerprint changed"
            )

        cls.cases = {
            item["id"]: item for item in cls.data["cases"]
        }

    def test_all_fourteen_reference_fixtures(self):
        self.assertEqual(len(self.cases), 14)

        for case_id, case in self.cases.items():
            with self.subTest(case=case_id):
                fixture = fixture_from_reference(case)
                self.assertTrue(validate_proposal(fixture))

                comparison = compare_to_reference(fixture, case)
                self.assertTrue(comparison["handling_match"])
                self.assertTrue(comparison["period_match"])
                self.assertTrue(comparison["obligations_match"])

    def test_omitted_discount_filter_detected(self):
        case = self.cases["S03"]
        candidate = fixture_from_reference(case)

        candidate["obligations"] = [
            item for item in candidate["obligations"]
            if item["code"] != "discount_code_population"
        ]

        # Deliberately incomplete but still structurally valid.
        # A plausible schema must not imply full coverage.
        candidate["handling"] = "SUPPORTED_CANDIDATE"
        self.assertTrue(validate_proposal(candidate))

        evaluation = compare_to_reference(candidate, case)
        self.assertFalse(evaluation["obligations_match"])
        self.assertFalse(evaluation["handling_match"])
        self.assertEqual(
            evaluation["missing_obligations"],
            ["discount_code_population"],
        )

    def test_omitted_cross_domain_obligations_detected(self):
        case = self.cases["S08"]
        candidate = fixture_from_reference(case)
        candidate["obligations"] = [
            item for item in candidate["obligations"]
            if item["code"] == "refund_measurement"
        ]
        candidate["handling"] = "SUPPORTED_CANDIDATE"

        self.assertTrue(validate_proposal(candidate))

        evaluation = compare_to_reference(candidate, case)
        self.assertEqual(
            evaluation["missing_obligations"],
            ["cross_domain_comparison", "customer_satisfaction"],
        )

    def test_wrong_period_detected(self):
        case = self.cases["S01"]
        candidate = fixture_from_reference(case)
        candidate["period"] = "2018-07"

        self.assertTrue(validate_proposal(candidate))

        evaluation = compare_to_reference(candidate, case)
        self.assertFalse(evaluation["period_match"])
        self.assertTrue(evaluation["obligations_match"])

    def test_unknown_obligation_is_not_silently_accepted_as_match(self):
        case = self.cases["S01"]
        candidate = fixture_from_reference(case)
        candidate["obligations"][0]["code"] = "imaginary_metric"

        self.assertTrue(validate_proposal(candidate))
        evaluation = compare_to_reference(candidate, case)

        self.assertFalse(evaluation["obligations_match"])
        self.assertEqual(
            evaluation["extra_obligations"],
            ["imaginary_metric"],
        )

    def test_invalid_contract_and_duplicate_obligations(self):
        candidate = fixture_from_reference(self.cases["S01"])

        changed = copy.deepcopy(candidate)
        changed["contract"] = "unknown.contract"
        with self.assertRaises(ValueError):
            validate_proposal(changed)

        changed = copy.deepcopy(candidate)
        changed["obligations"].append(
            copy.deepcopy(changed["obligations"][0])
        )
        with self.assertRaises(ValueError):
            validate_proposal(changed)

    def test_false_authorization_claims_rejected(self):
        candidate = fixture_from_reference(self.cases["S01"])
        for field, value in (
            ("execution_authorized", True),
            ("completion_eligible", True),
            ("evidence_state", "VERIFIED"),
        ):
            with self.subTest(field=field):
                changed = copy.deepcopy(candidate)
                changed[field] = value
                with self.assertRaises(ValueError):
                    validate_proposal(changed)

    def test_unsupported_must_expose_capability_gap(self):
        candidate = fixture_from_reference(self.cases["S03"])
        candidate["obligations"][1]["capability_state"] = "KNOWN_LABEL"

        with self.assertRaises(ValueError):
            validate_proposal(candidate)

    def test_security_proposal_cannot_carry_period(self):
        candidate = fixture_from_reference(self.cases["S12"])
        candidate["period"] = "2018-06"

        with self.assertRaises(ValueError):
            validate_proposal(candidate)


if __name__ == "__main__":
    unittest.main(verbosity=2)
