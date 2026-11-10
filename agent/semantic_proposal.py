"""Non-executable semantic proposal contract and reference evaluator.

Schema validation proves neither semantic completeness nor evidence support.
The reference evaluator is for offline testing, not production authorization.
"""

import re

CONTRACT = "opslens.semantic-proposal.v1"

HANDLINGS = {
    "SUPPORTED_CANDIDATE",
    "UNSUPPORTED_SCOPE",
    "UNSUPPORTED_CAUSAL",
    "CLARIFICATION_REQUIRED",
    "SECURITY_GUIDANCE",
    "REJECTED",
    "SCOPE_REVIEW_REQUIRED",
}

STATES = {
    "KNOWN_LABEL",
    "UNVERIFIED_CAPABILITY",
    "REVIEW_REQUIRED",
}

CODE_RE = re.compile(r"^[a-z][a-z0-9_]*$")


def validate_proposal(proposal):
    """Validate shape and safety invariants only."""
    if not isinstance(proposal, dict):
        raise ValueError("Proposal must be a dictionary")

    fields = {
        "contract",
        "handling",
        "period",
        "obligations",
        "execution_authorized",
        "evidence_state",
        "completion_eligible",
    }
    if set(proposal) != fields:
        raise ValueError("Missing or unexpected proposal fields")

    if proposal["contract"] != CONTRACT:
        raise ValueError("Unknown contract version")

    if proposal["handling"] not in HANDLINGS:
        raise ValueError("Unknown handling classification")

    if proposal["execution_authorized"] is not False:
        raise ValueError("Execution is never authorized")

    if proposal["completion_eligible"] is not False:
        raise ValueError("Completion cannot be certified")

    if proposal["evidence_state"] != "NOT_ASSESSED":
        raise ValueError("Evidence cannot be claimed")

    period = proposal["period"]
    if period is not None and (
        not isinstance(period, str)
        or re.fullmatch(r"\d{4}-(?:0[1-9]|1[0-2])", period) is None
    ):
        raise ValueError("Invalid month period")

    obligations = proposal["obligations"]
    if not isinstance(obligations, list) or not obligations:
        raise ValueError("Obligations must be a nonempty list")

    seen = set()
    for obligation in obligations:
        if not isinstance(obligation, dict) or set(obligation) != {
            "code", "capability_state"
        }:
            raise ValueError("Invalid obligation structure")

        code = obligation["code"]
        state = obligation["capability_state"]

        if not isinstance(code, str) or not CODE_RE.fullmatch(code):
            raise ValueError("Invalid obligation identifier")

        if code in seen:
            raise ValueError("Duplicate obligation")
        seen.add(code)

        if state not in STATES:
            raise ValueError("Invalid capability state")

    if proposal["handling"] in {
        "UNSUPPORTED_SCOPE",
        "UNSUPPORTED_CAUSAL",
    } and not any(
        item["capability_state"] == "UNVERIFIED_CAPABILITY"
        for item in obligations
    ):
        raise ValueError(
            "Unsupported proposal must expose an unverified capability"
        )

    if proposal["handling"] in {
        "CLARIFICATION_REQUIRED",
        "SCOPE_REVIEW_REQUIRED",
    } and not any(
        item["capability_state"] == "REVIEW_REQUIRED"
        for item in obligations
    ):
        raise ValueError(
            "Unresolved proposal must expose a review obligation"
        )

    if proposal["handling"] in {
        "SECURITY_GUIDANCE", "REJECTED"
    } and period is not None:
        raise ValueError("Security classifications cannot specify a period")

    if proposal["handling"] == "SUPPORTED_CANDIDATE" and any(
        item["capability_state"] != "KNOWN_LABEL"
        for item in obligations
    ):
        raise ValueError(
            "Supported candidates cannot contain unresolved capabilities"
        )

    return True


def compare_to_reference(proposal, reference):
    """Offline comparison against independent reference annotations.

    Never use a reference match as proof of real-world evidence,
    model correctness, or permission to execute.
    """
    validate_proposal(proposal)

    if not isinstance(reference, dict):
        raise ValueError("Reference must be a dictionary")

    required = {"handling", "period", "obligations"}
    if not required.issubset(reference):
        raise ValueError("Incomplete reference")

    expected = reference["obligations"]
    if (
        not isinstance(expected, list)
        or not expected
        or any(not isinstance(code, str) for code in expected)
        or len(expected) != len(set(expected))
    ):
        raise ValueError("Invalid reference obligations")

    proposed = [item["code"] for item in proposal["obligations"]]
    expected_set = set(expected)
    proposed_set = set(proposed)

    return {
        "handling_match": proposal["handling"] == reference["handling"],
        "period_match": proposal["period"] == reference["period"],
        "obligations_match": proposed_set == expected_set,
        "missing_obligations": sorted(expected_set - proposed_set),
        "extra_obligations": sorted(proposed_set - expected_set),
        "reference_coverage_fraction": (
            len(expected_set & proposed_set) / len(expected_set)
        ),
        "execution_authorized": False,
        "evidence_state": "NOT_ASSESSED",
        "completion_eligible": False,
    }
