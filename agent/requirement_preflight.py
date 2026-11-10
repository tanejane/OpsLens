"""Advisory preflight for requirement identification.

No tools, permissions, SQL, evidence claims, or runtime mutations.
PASS is not an authorization or coverage-completeness decision.
"""

import re


def inspect_question(question):
    def result(decision, reason):
        return {
            "contract": "opslens.requirement-preflight.v1",
            "decision": decision,
            "reason": reason,
            "execution_authorized": False,
            "evidence_state": "NOT_ASSESSED",
        }

    if not isinstance(question, str) or not question.strip():
        return result("UNSUPPORTED_SCOPE", "Invalid question")

    q = " ".join(question.lower().split())

    document = re.search(
        r"\b(?:untrusted|third.party|vendor)\b.{0,50}"
        r"\b(?:note|document)\b",
        q,
    )

    guidance_request = re.search(
        r"\b(?:how should|what should|how do we)\b"
        r".{0,100}\b(?:handle|treat|respond|do)\b"
        r"|\bhow should (?:it|this|we)\b",
        q,
    )

    instruction_risk = re.search(
        r"\b(?:secrets?|private instructions|"
        r"hidden instructions|system instructions|"
        r"financial write|database write)\b",
        q,
    )

    # Describing an untrusted instruction and asking how to
    # handle it is different from following that instruction.
    if document and guidance_request and instruction_risk:
        return result(
            "SECURITY_GUIDANCE",
            "Question requests safe handling of untrusted content",
        )

    override = re.search(
        r"\b(?:ignore|disregard|override|bypass)\b"
        r".{0,35}\b(?:instructions|rules|safeguards)\b"
        r"|\b(?:reveal|disclose|print|show)\b"
        r".{0,35}\b(?:hidden|system|private)\s+instructions\b",
        q,
    )

    if override:
        return result(
            "INSTRUCTION_OVERRIDE",
            "Instruction override or private-instruction request",
        )

    unsupported = (
        (
            r"\b(?:enterprise|first.time|vip)\s+"
            r"(?:customers?|buyers?)\b"
        ),
        r"\b(?:shipped|delivered|sent)\s+to\s+",
        r"\b(?:above|below|over|under)\s+(?:rm|myr|\$)\s*\d",
        r"\bweight(?:ed|ing)?\s+by\b",
        r"\b(?:marketing expenditure|marketing spend)\b",
        r"\b(?:refunds?|returns?)\b.{0,60}"
        r"\b(?:by customer segment|by region|by category)\b",
    )

    if any(re.search(pattern, q) for pattern in unsupported):
        return result(
            "UNSUPPORTED_SCOPE",
            "An additional analytical filter, dimension, "
            "weighting or domain was detected",
        )

    return result(
        "PASS",
        "No recognized preflight blocker; further validation required",
    )
