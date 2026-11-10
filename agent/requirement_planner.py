"""Versioned, non-executable requirement-planning interface.

This module composes existing rules but does not authorize tools,
validate evidence, or certify that an investigation is complete.
"""

from agent.requirement_preflight import inspect_question
from agent.requirement_extractor import extract


CONTRACT = "opslens.requirement-plan.v1"

DECISIONS = {
    "READY",
    "UNSUPPORTED_REQUIREMENTS",
    "NEEDS_CLARIFICATION",
    "ABSTAIN",
    "SECURITY_GUIDANCE",
    "REJECTED",
}

SECURITY_REQUIREMENTS = [
    "untrusted_instruction_recognition",
    "no_secret_disclosure",
    "no_financial_write_approval",
    "safe_evidence_handling",
]


def _gap(code, explanation):
    return {"code": code, "explanation": explanation}


def validate_plan(plan):
    """Raise ValueError for an invalid plan; return True otherwise."""
    if not isinstance(plan, dict):
        raise ValueError("Plan must be a dictionary")

    required_fields = {
        "contract",
        "decision",
        "intent",
        "requirements",
        "unresolved_requirements",
        "period_labels",
        "preflight_decision",
        "extraction_status",
        "execution_authorized",
        "evidence_state",
        "completion_eligible",
    }

    if set(plan) != required_fields:
        raise ValueError("Unexpected or missing plan fields")

    if plan["contract"] != CONTRACT:
        raise ValueError("Unknown plan contract")

    if plan["decision"] not in DECISIONS:
        raise ValueError("Unknown planner decision")

    if (
        not isinstance(plan["execution_authorized"], bool)
        or plan["execution_authorized"]
    ):
        raise ValueError("Planner must not authorize execution")

    if (
        not isinstance(plan["completion_eligible"], bool)
        or plan["completion_eligible"]
    ):
        raise ValueError("Planner must not certify completion")

    if plan["evidence_state"] != "NOT_ASSESSED":
        raise ValueError("Planner cannot claim verified evidence")

    if plan["intent"] is not None and not isinstance(
        plan["intent"], str
    ):
        raise ValueError("Invalid intent")

    for field in ("requirements", "period_labels"):
        values = plan[field]
        if not isinstance(values, list):
            raise ValueError(f"{field} must be a list")
        if any(
            not isinstance(value, str) or not value.strip()
            for value in values
        ):
            raise ValueError(f"{field} contains an invalid value")
        if len(values) != len(set(values)):
            raise ValueError(f"{field} contains duplicates")

    gaps = plan["unresolved_requirements"]
    if not isinstance(gaps, list):
        raise ValueError("Invalid unresolved requirements")

    for gap in gaps:
        if (
            not isinstance(gap, dict)
            or set(gap) != {"code", "explanation"}
            or not all(
                isinstance(value, str) and value.strip()
                for value in gap.values()
            )
        ):
            raise ValueError("Malformed unresolved requirement")

    if plan["preflight_decision"] not in {
        "PASS",
        "UNSUPPORTED_SCOPE",
        "INSTRUCTION_OVERRIDE",
        "SECURITY_GUIDANCE",
    }:
        raise ValueError("Unknown preflight decision")

    if plan["extraction_status"] is not None and (
        plan["extraction_status"] not in {
            "EXTRACTED",
            "EXTRACTED_UNSUPPORTED",
            "CLARIFICATION_REQUIRED",
            "ABSTAIN",
            "SECURITY_GUIDANCE",
            "UNAUTHORIZED_ACTION",
        }
    ):
        raise ValueError("Unknown extraction status")

    if plan["decision"] == "READY":
        if (
            not plan["intent"]
            or not plan["requirements"]
            or not plan["period_labels"]
            or plan["unresolved_requirements"]
            or plan["extraction_status"] != "EXTRACTED"
            or plan["preflight_decision"] != "PASS"
        ):
            raise ValueError("READY plan has incomplete fields")

    if plan["decision"] == "UNSUPPORTED_REQUIREMENTS":
        if not gaps:
            raise ValueError("Unsupported requirements must be visible")

    if plan["decision"] in {"ABSTAIN", "NEEDS_CLARIFICATION"}:
        if not gaps:
            raise ValueError("Unresolved decision must explain the gap")

    if plan["decision"] in {
        "SECURITY_GUIDANCE", "REJECTED"
    } and plan["period_labels"]:
        raise ValueError("Security decisions must not carry periods")

    # Security decisions must have coherent, closed obligations.
    # This prevents a valid-looking security decision from
    # carrying unrelated analytical requirements.
    if plan["decision"] == "REJECTED":
        if (
            plan["intent"] != "unauthorized_action"
            or plan["requirements"] != ["reject_unapproved_write"]
            or plan["unresolved_requirements"]
        ):
            raise ValueError("Inconsistent REJECTED plan")

        if not (
            (
                plan["preflight_decision"] == "INSTRUCTION_OVERRIDE"
                and plan["extraction_status"] is None
            )
            or (
                plan["preflight_decision"] == "PASS"
                and plan["extraction_status"] == "UNAUTHORIZED_ACTION"
            )
        ):
            raise ValueError("Inconsistent rejection provenance")

    if plan["decision"] == "SECURITY_GUIDANCE":
        if (
            plan["intent"] != "security_guidance"
            or plan["requirements"] != SECURITY_REQUIREMENTS
            or plan["unresolved_requirements"]
        ):
            raise ValueError("Inconsistent SECURITY_GUIDANCE plan")

        if not (
            (
                plan["preflight_decision"] == "SECURITY_GUIDANCE"
                and plan["extraction_status"] is None
            )
            or (
                plan["preflight_decision"] == "PASS"
                and plan["extraction_status"] == "SECURITY_GUIDANCE"
            )
        ):
            raise ValueError("Inconsistent guidance provenance")

    return True


def plan_question(question):
    pre = inspect_question(question)
    predecision = pre["decision"]

    decision = None
    intent = None
    requirements = []
    gaps = []
    periods = []
    extraction_status = None

    if predecision == "UNSUPPORTED_SCOPE":
        decision = "ABSTAIN"
        gaps = [
            _gap(
                "UNPARSED_ANALYTICAL_SCOPE",
                pre["reason"],
            )
        ]

    elif predecision == "INSTRUCTION_OVERRIDE":
        decision = "REJECTED"
        intent = "unauthorized_action"
        requirements = ["reject_unapproved_write"]

    elif predecision == "SECURITY_GUIDANCE":
        decision = "SECURITY_GUIDANCE"
        intent = "security_guidance"
        requirements = list(SECURITY_REQUIREMENTS)

    elif predecision == "PASS":
        extracted = extract(question)
        extraction_status = extracted["status"]
        intent = extracted["intent"]
        requirements = list(extracted["requirements"])
        periods = list(extracted["period_labels"])

        if extraction_status == "EXTRACTED":
            decision = "READY"

        elif extraction_status == "EXTRACTED_UNSUPPORTED":
            decision = "UNSUPPORTED_REQUIREMENTS"

            adapters = extracted["registered_adapters"]
            gaps = [
                _gap(
                    requirement,
                    "No registered evidence adapter",
                )
                for requirement in requirements
                if adapters.get(requirement) is None
            ]

            if not gaps:
                gaps = [
                    _gap(
                        "UNVERIFIED_ANALYTICAL_CAPABILITY",
                        "Extraction reports unsupported requirements",
                    )
                ]

        elif extraction_status == "CLARIFICATION_REQUIRED":
            decision = "NEEDS_CLARIFICATION"
            gaps = [
                _gap(
                    "MISSING_REQUIRED_CONTEXT",
                    extracted["reason"] or "Clarification required",
                )
            ]

        elif extraction_status == "ABSTAIN":
            decision = "ABSTAIN"
            gaps = [
                _gap(
                    "UNRESOLVED_ANALYTICAL_SCOPE",
                    extracted["reason"] or "Question cannot be represented",
                )
            ]

        elif extraction_status == "SECURITY_GUIDANCE":
            decision = "SECURITY_GUIDANCE"
            intent = "security_guidance"
            requirements = list(SECURITY_REQUIREMENTS)
            periods = []

        elif extraction_status == "UNAUTHORIZED_ACTION":
            decision = "REJECTED"
            intent = "unauthorized_action"
            requirements = ["reject_unapproved_write"]
            periods = []

        else:
            raise ValueError("Unsupported extraction status")

    else:
        raise ValueError("Unsupported preflight decision")

    result = {
        "contract": CONTRACT,
        "decision": decision,
        "intent": intent,
        "requirements": requirements,
        "unresolved_requirements": gaps,
        "period_labels": periods,
        "preflight_decision": predecision,
        "extraction_status": extraction_status,
        "execution_authorized": False,
        "evidence_state": "NOT_ASSESSED",
        "completion_eligible": False,
    }

    validate_plan(result)
    return result
