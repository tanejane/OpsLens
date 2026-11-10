"""Reviewed obligation aliases for OFFLINE evaluation only.

Aliases do not prove capability, verify evidence, or authorize
execution. Raw candidate identifiers remain unchanged.
"""

from agent.semantic_proposal import (
    compare_to_reference,
    validate_proposal,
)

REVIEWED_ALIASES = {
    "discount_codes_filter": "discount_code_population",
}


def evaluate_with_aliases(candidate, reference):
    validate_proposal(candidate)

    # First preserve the original exact comparison.
    exact = compare_to_reference(candidate, reference)

    raw_codes = [
        item["code"] for item in candidate["obligations"]
    ]

    normalized = [
        REVIEWED_ALIASES.get(code, code)
        for code in raw_codes
    ]

    # Detect collisions: two distinct model obligations must
    # never collapse silently into one reference obligation.
    if len(normalized) != len(set(normalized)):
        raise ValueError("Alias normalization collision")

    expected = set(reference["obligations"])
    observed = set(normalized)

    aliases_used = [
        {
            "original": original,
            "reference": mapped,
        }
        for original, mapped in zip(raw_codes, normalized)
        if original != mapped
    ]

    return {
        "contract": "opslens.semantic-alias-evaluation.v1",
        "exact": exact,
        "normalized_obligations_match": observed == expected,
        "normalized_missing": sorted(expected - observed),
        "normalized_extra": sorted(observed - expected),
        "aliases_used": aliases_used,
        "raw_obligations": raw_codes,
        "normalized_obligations": normalized,
        "handling_match": exact["handling_match"],
        "period_match": exact["period_match"],
        "execution_authorized": False,
        "completion_eligible": False,
        "evidence_state": "NOT_ASSESSED",
        "evaluation_only": True,
    }
