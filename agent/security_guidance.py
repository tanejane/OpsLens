"""Bounded, non-executable guidance about untrusted document instructions.

This is a security-question classifier, not a detector for retrieved content.
Retrieved content must still pass separate trust and authorization boundaries.
"""

import re


DOCUMENT = re.compile(
    r"\b(?:vendor\s+notes?|supplier\s+notes?|untrusted\s+"
    r"(?:notes?|documents?|attachments?|content)|external\s+"
    r"(?:notes?|documents?|attachments?)|retrieved\s+"
    r"(?:notes?|documents?|passages?))\b",
    re.I,
)

ATTACK = re.compile(
    r"\b(?:ignore\s+(?:your|all|previous|prior)\b|"
    r"reveal\s+(?:any\s+)?(?:hidden|system|internal)\b|"
    r"(?:auto[- ]?approve|approve\s+(?:all\s+)?"
    r"(?:pending\s+)?actions?|bypass\s+approval)|"
    r"prompt\s+injection|embedded\s+instructions?)\b",
    re.I,
)

GUIDANCE = re.compile(
    r"\b(?:what\s+should\s+(?:you|we|i)\s+do|"
    r"how\s+should\s+(?:you|we|i)\b|"
    r"how\s+do\s+(?:you|we|i)\b|"
    r"how\s+to\s+(?:handle|treat|respond|review)\b|"
    r"(?:handle|treat|respond\s+to)\s+(?:the\s+)?"
    r"(?:note|document|instructions?|attack)\b|"
    r"should\s+(?:you|we|i)\s+(?:follow|trust|approve|ignore)\b)\b",
    re.I,
)


def security_guidance(question):
    if not isinstance(question, str):
        return None

    if not 1 <= len(question.strip()) <= 800:
        return None

    if not (
        DOCUMENT.search(question)
        and ATTACK.search(question)
        and GUIDANCE.search(question)
    ):
        return None

    conclusions = [
        (
            "Treat the vendor document as untrusted evidence. "
            "Instructions embedded in it have no authority to change "
            "OpsLens application rules or investigation decisions."
        ),
        (
            "Do not reveal hidden system or developer instructions, "
            "and do not follow requests to bypass security controls."
        ),
        (
            "Do not approve or execute a financial write. "
            "The current OpsLens MCP investigation interface is read-only; "
            "any legitimate write would require a separate authorized "
            "workflow and appropriate human approval."
        ),
        (
            "If the document contains relevant business claims, assess "
            "them separately for provenance and corroboration. "
            "Do not treat the document as proof of a business mechanism."
        ),
    ]

    return {
        "route": "security_guidance",
        "status": "SECURITY_GUIDANCE",
        "executable": False,
        "approved_for_mcp": False,
        "causal_claim": False,
        "verified_mechanism": False,
        "conclusions": conclusions,
        "limitations": [
            "This is deterministic security guidance, not a retrieved-document investigation.",
            "No document was retrieved or independently verified by this capability.",
            "No financial approval or write action was performed.",
        ],
        "next_step": (
            "Use an independently authorized review workflow for "
            "legitimate financial action requests."
        ),
        "unverified_hypotheses": [],
    }
