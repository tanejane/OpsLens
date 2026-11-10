
"""Conservative offline capability boundary.

No registered capabilities are supplied in this prototype.
This module never authorizes execution or verifies evidence.
"""

from agent.structured_semantic_intent import validate_intent


def assess_capability(intent):
    validate_intent(intent)

    claimed = intent["handling"]

    if claimed == "CLARIFICATION_REQUIRED":
        decision = "CLARIFICATION_REQUIRED"
        reason = "Unresolved user-supplied information"

    elif claimed == "UNSUPPORTED_CAUSAL":
        decision = "CAUSAL_REVIEW_REQUIRED"
        reason = "Causal identification is not independently verified"

    elif claimed == "SCOPE_REVIEW_REQUIRED":
        decision = "SCOPE_REVIEW_REQUIRED"
        reason = "Semantic scope requires further review"

    else:
        decision = "CAPABILITY_NOT_VERIFIED"
        reason = (
            "No independent metric, field, operator or "
            "adapter capability registry has been checked"
        )

    return {
        "contract": "opslens.capability-assessment.v1",
        "model_claimed_handling": claimed,
        "decision": decision,
        "reason": reason,
        "model_claimed_supported": (
            claimed == "SUPPORTED_CANDIDATE"
        ),
        "support_claim_unverified": (
            claimed == "SUPPORTED_CANDIDATE"
        ),
        "execution_authorized": False,
        "completion_eligible": False,
        "evidence_state": "NOT_ASSESSED",
        "capability_registry_checked": False,
    }
