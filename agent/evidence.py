
from __future__ import annotations
from dataclasses import dataclass
from typing import Any
from agent.state import EvidenceStrength, HypothesisStatus

@dataclass(frozen=True)
class EvidenceAssessment:
    evidence_item: dict[str, Any]
    hypothesis_status: HypothesisStatus
    confidence: float

def _pct(prev: float, cur: float):
    return None if prev == 0 else ((cur - prev) / abs(prev)) * 100.0

def assess_cogs_vs_revenue(result: dict[str, Any]) -> EvidenceAssessment:
    if not result.get("ok"):
        raise ValueError(result.get("error"))
    rows = result["data"]["rows"]
    if len(rows) < 2:
        raise ValueError("Need two monthly rows.")

    a, b = rows[0], rows[-1]
    rg = _pct(float(a["revenue"] or 0), float(b["revenue"] or 0))
    cg = _pct(float(a["cogs"] or 0), float(b["cogs"] or 0))

    if rg is not None and cg is not None and cg > rg + 1.0:
        status = HypothesisStatus.SUPPORTED
        strength = EvidenceStrength.STRONG
        confidence = min(0.95, 0.65 + (cg-rg)/20)
        claim = "COGS increased faster than revenue, supporting deteriorating unit economics."
    elif rg is not None and cg is not None and cg > rg:
        status = HypothesisStatus.WEAK
        strength = EvidenceStrength.MODERATE
        confidence = 0.55
        claim = "COGS increased slightly faster than revenue."
    else:
        status = HypothesisStatus.REJECTED
        strength = EvidenceStrength.MODERATE
        confidence = 0.75
        claim = "COGS did not increase faster than revenue."

    return EvidenceAssessment(
        {
            "evidence_id": "E-H1-COGS-GROWTH",
            "source_type": "sql",
            "source_ref": "semantic.order_economics",
            "claim": claim,
            "value": {
                "revenue_growth_pct": None if rg is None else round(rg, 2),
                "cogs_growth_pct": None if cg is None else round(cg, 2),
            },
            "supports_hypotheses": ["H1"] if status != HypothesisStatus.REJECTED else [],
            "contradicts_hypotheses": ["H1"] if status == HypothesisStatus.REJECTED else [],
            "strength": strength,
            "limitations": [
                "Temporal evidence alone is not causal proof.",
                "Supplier-specific attribution still needs corroboration."
            ],
        },
        status,
        round(confidence, 2),
    )

def assess_profitability_pattern(result: dict[str, Any]) -> EvidenceAssessment:
    if not result.get("ok"):
        raise ValueError(result.get("error"))
    rows = result["data"]["rows"]
    if len(rows) < 2:
        raise ValueError("Need two monthly rows.")

    a, b = rows[0], rows[-1]
    rg = _pct(float(a["revenue"] or 0), float(b["revenue"] or 0))
    pg = _pct(float(a["contribution_profit"] or 0), float(b["contribution_profit"] or 0))
    md = (float(b["contribution_margin"] or 0) - float(a["contribution_margin"] or 0)) * 100
    confirmed = rg is not None and pg is not None and rg > 0 and pg < 0 and md < 0

    status = HypothesisStatus.SUPPORTED if confirmed else HypothesisStatus.WEAK
    return EvidenceAssessment(
        {
            "evidence_id": "E-OUTCOME-PATTERN",
            "source_type": "sql",
            "source_ref": "semantic.daily_commerce",
            "claim": (
                "Revenue increased while contribution profit and margin deteriorated."
                if confirmed else
                "The requested profitability pattern was not fully confirmed."
            ),
            "value": {
                "revenue_growth_pct": None if rg is None else round(rg, 2),
                "contribution_profit_growth_pct": None if pg is None else round(pg, 2),
                "contribution_margin_delta_pp": round(md, 2),
            },
            "supports_hypotheses": ["H1","H2","H3","H4"] if confirmed else [],
            "contradicts_hypotheses": [],
            "strength": EvidenceStrength.STRONG if confirmed else EvidenceStrength.WEAK,
            "limitations": ["Outcome confirmation does not identify the cause."],
        },
        status,
        0.95 if confirmed else 0.4,
    )
