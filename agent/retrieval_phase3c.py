
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

from agent.mcp_bridge import OpsLensMCPBridge


PROMPT_INJECTION_PATTERNS = [
    r"ignore (all |any |the )?previous",
    r"reveal (the )?(system|developer) (prompt|instructions)",
    r"auto[- ]?approve",
    r"bypass (the )?(rules|policy|approval)",
    r"do not follow",
    r"\bignore\s+(?:your|the|all|any)\s+(?:rules|instructions)\b",
    r"\breveal\s+(?:the\s+)?(?:hidden|internal)\s+(?:instructions|prompt)\b",
    r"\bignore\s+(?:all\s+)?prior\s+(?:rules|instructions)\b",
    r"\breveal\s+(?:any\s+)?hidden\s+system\s+instructions\b",
    r"\bapprove\s+all\s+pending\s+actions\s+automatically\b",
]


@dataclass(frozen=True)
class RankedDocument:
    document_id: str
    filename: str
    content: str
    source_type: str
    trust_level: str
    score: float
    precedence_reason: str
    instruction_like_content: bool


def _quote_sql_literal(value: str) -> str:
    return "'" + value.replace("'", "''") + "'"


def _looks_like_prompt_injection(text: str) -> bool:
    low = text.lower()
    return any(re.search(p, low) for p in PROMPT_INJECTION_PATTERNS)


def rank_document(row: dict[str, Any]) -> RankedDocument:
    filename = str(row.get("filename") or "")
    content = str(row.get("content") or "")
    trust_level = str(row.get("trust_level") or "unknown")

    low_name = filename.lower()
    low_content = content.lower()

    score = 0.50
    reasons: list[str] = []

    if trust_level == "internal":
        score += 0.25
        reasons.append("internal source")
    elif trust_level == "untrusted_external":
        score -= 0.20
        reasons.append("untrusted external source")

    if "corrected" in low_name or "corrected" in low_content:
        score += 0.20
        reasons.append("explicitly corrected/reviewed")

    if "stale" in low_name or "preliminary" in low_content:
        score -= 0.20
        reasons.append("stale/preliminary")

    instruction_like = _looks_like_prompt_injection(content)
    if instruction_like:
        score -= 0.30
        reasons.append("instruction-like content")

    return RankedDocument(
        document_id=str(row.get("document_id") or ""),
        filename=filename,
        content=content,
        source_type=str(row.get("source_type") or ""),
        trust_level=trust_level,
        score=max(0.0, min(1.0, score)),
        precedence_reason=", ".join(reasons) if reasons else "default score",
        instruction_like_content=instruction_like,
    )


async def search_documents(
    terms: list[str],
    purpose: str,
    max_rows: int = 20,
) -> list[RankedDocument]:
    if not terms:
        return []

    clauses = []
    for term in terms:
        lit = _quote_sql_literal(f"%{term}%")
        clauses.append(f"(filename ILIKE {lit} OR content ILIKE {lit})")

    query = f"""
        SELECT
            document_id,
            filename,
            content,
            source_type,
            trust_level
        FROM knowledge.documents
        WHERE {" OR ".join(clauses)}
        ORDER BY filename
    """

    result = await OpsLensMCPBridge().call(
        "run_readonly_sql",
        {
            "query": query,
            "purpose": purpose,
            "expected_grain": "one row per retrieved document",
            "max_rows": max_rows,
        },
    )

    if not result.get("ok"):
        raise RuntimeError(result.get("error") or "Document retrieval failed")

    return sorted(
        [rank_document(row) for row in result["data"]["rows"]],
        key=lambda d: (d.score, d.filename),
        reverse=True,
    )


def supplier_cost_relevant(doc: RankedDocument) -> bool:
    """
    Conservative H1 corroboration rule.

    Supplier-related words alone are not enough. Require explicit cost-pressure
    language, preventing invoice-reconciliation or generic forecast documents
    from being promoted to causal evidence.
    """
    text = f"{doc.filename} {doc.content}".lower()

    explicit_patterns = [
        "supplier cost increase",
        "supplier_cost_notice",
        "cost increase",
        "cost pressure",
        "supplier price increase",
        "supplier prices increased",
    ]

    return (
        doc.trust_level == "internal"
        and not doc.instruction_like_content
        and any(pattern in text for pattern in explicit_patterns)
    )


def campaign_relevant(doc: RankedDocument) -> bool:
    text = f"{doc.filename} {doc.content}".lower()

    return (
        doc.trust_level == "internal"
        and not doc.instruction_like_content
        and (
            "growthmax" in text
            or "campaign brief" in text
            or "campaign spend" in text
        )
    )
