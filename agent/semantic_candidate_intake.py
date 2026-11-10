"""Untrusted semantic-candidate JSON intake.

Parses and validates candidate proposals. Never grants tool authority.
KNOWN_LABEL means known vocabulary, NOT proven evidence capability.
"""

import json

from agent.semantic_proposal import validate_proposal


MAX_BYTES = 16384
MAX_OBLIGATIONS = 32

# Controlled vocabulary, independent of the benchmark file.
# Membership is NOT evidence of an executable capability.
KNOWN_VOCABULARY = frozenset({
    "refund_rate",
    "refund_measurement",
    "seller_breakdown",
    "late_delivery_rate",
    "late_delivery_measurement",
    "noncausal_interpretation",
    "causal_identification",
    "seller_causal_identification",
    "year_clarification",
    "untrusted_content_recognition",
    "protect_private_instructions",
    "reject_unapproved_write",
    "reject_instruction_override",
})

SECURITY_GUIDANCE_CODES = frozenset({
    "untrusted_content_recognition",
    "protect_private_instructions",
    "reject_unapproved_write",
})


def _reject_duplicate_keys(pairs):
    value = {}
    for key, item in pairs:
        if key in value:
            raise ValueError("Duplicate JSON key")
        value[key] = item
    return value


def _reject_constant(value):
    raise ValueError("Invalid JSON numeric constant")


def accept_candidate(raw):
    """Accept only a bounded, valid, non-authoritative proposal."""
    if not isinstance(raw, str):
        raise ValueError("Candidate must be a JSON string")

    if len(raw.encode("utf-8")) > MAX_BYTES:
        raise ValueError("Candidate exceeds size limit")

    try:
        proposal = json.loads(
            raw,
            object_pairs_hook=_reject_duplicate_keys,
            parse_constant=_reject_constant,
        )
    except (json.JSONDecodeError, UnicodeError) as error:
        raise ValueError("Malformed candidate JSON") from error

    validate_proposal(proposal)

    obligations = proposal["obligations"]
    if len(obligations) > MAX_OBLIGATIONS:
        raise ValueError("Too many obligations")

    for item in obligations:
        code = item["code"]
        state = item["capability_state"]

        if (
            state == "KNOWN_LABEL"
            and code not in KNOWN_VOCABULARY
        ):
            raise ValueError(
                "Unknown code cannot claim KNOWN_LABEL"
            )

    codes = {item["code"] for item in obligations}

    if proposal["handling"] == "REJECTED":
        if codes != {"reject_instruction_override"}:
            raise ValueError(
                "REJECTED must contain only rejection obligation"
            )

    if proposal["handling"] == "SECURITY_GUIDANCE":
        if codes != SECURITY_GUIDANCE_CODES:
            raise ValueError(
                "Incomplete or contaminated security guidance"
            )

    # Return validated data, not an authorization decision.
    return proposal
