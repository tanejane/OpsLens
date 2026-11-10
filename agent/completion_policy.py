"""Conservative, advisory-only stopping policy.

This module does not execute tools or alter investigation results.
It uses explicitly registered requirement specifications.
"""

from agent.evidence_coverage import evaluate


def recommend(response, specification):
    """Recommend a stop reason; never authorize execution."""

    if specification is None:
        return {
            "decision": "COVERAGE_NOT_ASSESSED",
            "coverage": None,
            "may_claim_complete": False,
            "reason": "No explicit requirement specification supplied",
        }

    if not isinstance(specification, dict):
        raise ValueError("Invalid completion specification")

    if set(specification) != {"period", "requirements"}:
        raise ValueError("Incomplete completion specification")

    coverage = evaluate(
        response,
        specification["period"],
        specification["requirements"],
    )

    if (
        coverage["decision"] == "COMPLETE_DESCRIPTIVE"
        and coverage["evaluation_complete"]
    ):
        decision = "QUESTION_ADDRESSED"
        reason = "All registered descriptive requirements have proof-backed coverage"

    elif coverage["requirements_satisfied"] > 0:
        decision = "QUESTION_PARTIALLY_ADDRESSED"
        reason = "Some requested requirements have validated evidence; gaps remain"

    else:
        decision = "QUESTION_NOT_DEMONSTRATED"
        reason = "No registered requirement has demonstrated proof-backed coverage"

    return {
        "decision": decision,
        "coverage": coverage,
        "may_claim_complete": decision == "QUESTION_ADDRESSED",
        "reason": reason,
    }
