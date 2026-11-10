
"""Offline structured semantic intent prototype.

Not a Gemini interface, capability verifier or executable plan.
"""

import re

KINDS = {"FILTER", "GROUPING", "COMPARISON"}
OPERATORS = {"eq", "gt", "gte", "lt", "lte", "in"}
HANDLINGS = {
    "SUPPORTED_CANDIDATE",
    "UNSUPPORTED_SCOPE",
    "UNSUPPORTED_CAUSAL",
    "CLARIFICATION_REQUIRED",
    "SCOPE_REVIEW_REQUIRED",
}


def validate_intent(intent):
    if not isinstance(intent, dict):
        raise ValueError("Intent must be an object")

    fields = {
        "contract", "handling", "metric", "period",
        "operations", "clarifications",
        "execution_authorized", "completion_eligible",
        "evidence_state",
    }
    if set(intent) != fields:
        raise ValueError("Unexpected intent fields")

    if intent["contract"] != "opslens.structured-intent.v1":
        raise ValueError("Invalid contract")

    if intent["handling"] not in HANDLINGS:
        raise ValueError("Invalid handling")

    if not isinstance(intent["metric"], str) or not re.fullmatch(
        r"[a-z][a-z0-9_]{0,79}", intent["metric"]
    ):
        raise ValueError("Invalid metric")

    period = intent["period"]
    if period is not None and (
        not isinstance(period, str)
        or not re.fullmatch(r"\d{4}-(0[1-9]|1[0-2])", period)
    ):
        raise ValueError("Invalid period")

    if intent["execution_authorized"] is not False:
        raise ValueError("Execution prohibited")

    if intent["completion_eligible"] is not False:
        raise ValueError("Completion prohibited")

    if intent["evidence_state"] != "NOT_ASSESSED":
        raise ValueError("Evidence cannot be claimed")

    operations = intent["operations"]
    if not isinstance(operations, list) or len(operations) > 16:
        raise ValueError("Invalid operations")

    seen = set()
    for op in operations:
        if not isinstance(op, dict):
            raise ValueError("Invalid operation")

        kind = op.get("kind")
        if kind not in KINDS:
            raise ValueError("Unknown operation kind")

        required = (
            {"kind", "field", "operator", "value"}
            if kind == "FILTER"
            else {"kind", "field"}
        )

        if set(op) != required:
            raise ValueError("Invalid operation fields")

        field = op["field"]
        if not isinstance(field, str) or not re.fullmatch(
            r"[a-z][a-z0-9_]{0,79}", field
        ):
            raise ValueError("Invalid operation field")

        if kind == "FILTER":
            if op["operator"] not in OPERATORS:
                raise ValueError("Invalid filter operator")

            value = op["value"]
            if type(value) not in (str, int, float):
                raise ValueError("Invalid filter value")

            if isinstance(value, str) and not (0 < len(value) <= 128):
                raise ValueError("Invalid filter value length")

        signature = repr(sorted(op.items()))
        if signature in seen:
            raise ValueError("Duplicate operation")
        seen.add(signature)

    clarifications = intent["clarifications"]
    if not isinstance(clarifications, list) or len(clarifications) > 8:
        raise ValueError("Invalid clarifications")

    if not all(
        isinstance(q, str) and 0 < len(q.strip()) <= 256
        for q in clarifications
    ):
        raise ValueError("Invalid clarification")

    if (
        intent["handling"] == "CLARIFICATION_REQUIRED"
    ) != bool(clarifications):
        raise ValueError("Clarification/handling inconsistency")

    return intent


def compare_intents(candidate, reference):
    """Exact field-level offline comparison; no semantic aliases."""
    validate_intent(candidate)
    validate_intent(reference)

    def signatures(intent):
        return {
            repr(sorted(op.items()))
            for op in intent["operations"]
        }

    expected = signatures(reference)
    actual = signatures(candidate)

    return {
        "handling_match": (
            candidate["handling"] == reference["handling"]
        ),
        "metric_match": candidate["metric"] == reference["metric"],
        "period_match": candidate["period"] == reference["period"],
        "operations_match": actual == expected,
        "missing_operations": sorted(expected - actual),
        "extra_operations": sorted(actual - expected),
        "clarification_required_match": (
            bool(candidate["clarifications"])
            == bool(reference["clarifications"])
        ),
        "parameter_fidelity_assessed": True,
        "execution_authorized": False,
    }
