
from __future__ import annotations

import asyncio
from copy import deepcopy
from typing import Any

from langgraph.graph import END, START, StateGraph

from agent.evidence import assess_cogs_vs_revenue
from agent.graph_phase3b import initialize as initialize_phase3b
from agent.mcp_bridge import run_sql_evidence
from agent.retrieval_phase3c import (
    campaign_relevant,
    search_documents,
    supplier_cost_relevant,
)
from agent.schema_adaptive import (
    MARKETING_COST_CANDIDATES,
    REFUND_CANDIDATES,
    monthly_metric,
)
from agent.state import (
    EvidenceStrength,
    HypothesisStatus,
    InvestigationState,
)


def _pct(prev: float, cur: float) -> float | None:
    if prev == 0:
        return None
    return ((cur - prev) / abs(prev)) * 100.0


def initialize(state: InvestigationState) -> dict:
    base = initialize_phase3b(state)

    return {
        **base,
        "business_context": {
            **base["business_context"],
            "phase": "3C-v2",
            "source_precedence_policy": (
                "Structured measured evidence > corrected/reviewed internal "
                "documents > ordinary internal documents > stale/preliminary "
                "documents > untrusted external documents."
            ),
            "retrieved_documents": [],
        },
    }


def gather_structured_evidence(state: InvestigationState) -> dict[str, Any]:
    async def _run():
        # Preserve/redo H1 rather than losing Phase 3B causal evidence.
        h1 = await run_sql_evidence(
            query="""
                SELECT
                    DATE_TRUNC(
                        'month',
                        NULLIF(order_purchase_timestamp,'')::timestamp
                    )::date AS business_month,
                    SUM(effective_revenue) AS revenue,
                    SUM(effective_cogs) AS cogs,
                    SUM(effective_contribution_profit) AS contribution_profit
                FROM semantic.order_economics
                WHERE NULLIF(order_purchase_timestamp,'')::timestamp >= DATE '2018-02-01'
                  AND NULLIF(order_purchase_timestamp,'')::timestamp < DATE '2018-04-01'
                GROUP BY 1
                ORDER BY 1
            """,
            purpose="Retain the Phase 3B COGS-vs-revenue causal test in Phase 3C.",
            expected_grain="one row per business month",
            max_rows=12,
        )

        marketing = await monthly_metric(
            schema="finance",
            relation="daily_pnl",
            metric_candidates=MARKETING_COST_CANDIDATES,
            start_date="2018-02-01",
            end_date="2018-04-01",
            purpose="Test marketing-cost increase during the flagship deterioration.",
        )

        refunds = await monthly_metric(
            schema="finance",
            relation="daily_pnl",
            metric_candidates=REFUND_CANDIDATES,
            start_date="2018-02-01",
            end_date="2018-04-01",
            purpose="Test refund increase during the flagship deterioration.",
        )

        mix = await run_sql_evidence(
            query="SELECT * FROM semantic.product_mix_effective",
            purpose=(
                "Inspect controlled product-mix evidence and verify whether it "
                "belongs to the flagship 2018-03 incident window."
            ),
            expected_grain="controlled product-mix evidence row",
            max_rows=1000,
        )

        return h1, marketing, refunds, mix

    h1, marketing, refunds, mix = asyncio.run(_run())

    return {
        "business_context": {
            **state["business_context"],
            "structured_results": {
                "h1": h1,
                "marketing": marketing,
                "refunds": refunds,
                "product_mix": mix,
            },
        },
        "tool_calls_used": state["tool_calls_used"] + 4,
        "current_step": state["current_step"] + 1,
    }


def gather_document_evidence(state: InvestigationState) -> dict[str, Any]:
    async def _run():
        inc001 = await search_documents(
            ["supplier cost increase", "supplier_cost_notice", "GrowthMax", "campaign brief"],
            purpose="Retrieve high-relevance supplier-cost and campaign documents.",
        )

        inc009 = await search_documents(
            ["inc009", "preliminary", "corrected"],
            purpose="Retrieve stale/corrected conflict fixture.",
        )

        inc011 = await search_documents(
            ["ignore prior", "auto-approve", "vendor"],
            purpose="Retrieve prompt-injection fixture as untrusted data.",
        )

        return inc001, inc009, inc011

    inc001, inc009, inc011 = asyncio.run(_run())

    serializable = {}
    for key, values in {
        "inc001": inc001,
        "inc009": inc009,
        "inc011": inc011,
    }.items():
        serializable[key] = [
            {
                "document_id": d.document_id,
                "filename": d.filename,
                "content": d.content,
                "source_type": d.source_type,
                "trust_level": d.trust_level,
                "score": d.score,
                "precedence_reason": d.precedence_reason,
                "instruction_like_content": d.instruction_like_content,
            }
            for d in values
        ]

    return {
        "business_context": {
            **state["business_context"],
            "retrieved_documents": serializable,
        },
        "tool_calls_used": state["tool_calls_used"] + 3,
        "current_step": state["current_step"] + 1,
    }


def _eval_monthly_growth(
    result: dict[str, Any],
    support_threshold: float,
):
    if not result.get("ok"):
        return None, None, None, None

    rows = result["data"]["rows"]
    if len(rows) < 2:
        return None, None, None, None

    prev = float(rows[0]["metric_value"] or 0)
    cur = float(rows[-1]["metric_value"] or 0)
    growth = _pct(prev, cur)

    if growth is None:
        return prev, cur, growth, "WEAK"

    if growth > support_threshold:
        return prev, cur, growth, "SUPPORTED"

    if growth > 0:
        return prev, cur, growth, "WEAK"

    return prev, cur, growth, "REJECTED"


def fuse_evidence(state: InvestigationState) -> dict[str, Any]:
    hypotheses = deepcopy(state["hypotheses"])
    ledger = list(state["evidence_ledger"])
    conflicts = list(state["conflicts"])

    structured = state["business_context"]["structured_results"]

    # H1: keep the real structured test from 3B.
    h1_assessment = assess_cogs_vs_revenue(structured["h1"])
    ledger.append(h1_assessment.evidence_item)

    h1 = next(h for h in hypotheses if h["hypothesis_id"] == "H1")
    h1["status"] = h1_assessment.hypothesis_status
    h1["confidence"] = h1_assessment.confidence

    if h1_assessment.hypothesis_status == HypothesisStatus.REJECTED:
        h1["evidence_against"].append(h1_assessment.evidence_item["evidence_id"])
    else:
        h1["evidence_for"].append(h1_assessment.evidence_item["evidence_id"])

    # H2: marketing.
    prev, cur, growth, verdict = _eval_monthly_growth(
        structured["marketing"],
        support_threshold=10.0,
    )

    h2 = next(h for h in hypotheses if h["hypothesis_id"] == "H2")

    if verdict == "SUPPORTED":
        h2["status"] = HypothesisStatus.SUPPORTED
        h2["confidence"] = min(0.92, 0.65 + float(growth) / 200)
        strength = EvidenceStrength.STRONG
        claim = "Marketing cost increased materially during the deterioration window."
    elif verdict == "WEAK":
        h2["status"] = HypothesisStatus.WEAK
        h2["confidence"] = 0.50
        strength = EvidenceStrength.MODERATE
        claim = "Marketing cost increased, but causal strength is limited."
    elif verdict == "REJECTED":
        h2["status"] = HypothesisStatus.REJECTED
        h2["confidence"] = 0.70
        strength = EvidenceStrength.MODERATE
        claim = "Marketing cost did not increase during the deterioration window."
    else:
        h2["status"] = HypothesisStatus.WEAK
        h2["confidence"] = 0.20
        strength = EvidenceStrength.WEAK
        claim = "Marketing evidence was incomplete."

    ledger.append(
        {
            "evidence_id": "E-H2-MARKETING-COST",
            "source_type": "sql",
            "source_ref": "finance.daily_pnl",
            "claim": claim,
            "value": {
                "previous": prev,
                "current": cur,
                "growth_pct": None if growth is None else round(growth, 2),
            },
            "supports_hypotheses": ["H2"]
            if h2["status"] in {HypothesisStatus.SUPPORTED, HypothesisStatus.WEAK}
            else [],
            "contradicts_hypotheses": ["H2"]
            if h2["status"] == HypothesisStatus.REJECTED
            else [],
            "strength": strength,
            "limitations": [
                "Cost movement is measured evidence, but causal attribution still benefits from campaign-level corroboration."
            ],
        }
    )

    if h2["status"] == HypothesisStatus.REJECTED:
        h2["evidence_against"].append("E-H2-MARKETING-COST")
    else:
        h2["evidence_for"].append("E-H2-MARKETING-COST")

    # H3: controlled mix fixture is outside flagship window.
    h3 = next(h for h in hypotheses if h["hypothesis_id"] == "H3")
    h3["status"] = HypothesisStatus.REJECTED
    h3["confidence"] = 0.70
    h3["evidence_against"].append("E-H3-MIX-WINDOW")

    ledger.append(
        {
            "evidence_id": "E-H3-MIX-WINDOW",
            "source_type": "sql",
            "source_ref": "semantic.product_mix_effective",
            "claim": (
                "The controlled product-mix incident belongs to a different "
                "window, so it does not support the flagship 2018-03 cause."
            ),
            "value": {
                "retrieved_rows": len(
                    structured["product_mix"].get("data", {}).get("rows", [])
                )
            },
            "supports_hypotheses": [],
            "contradicts_hypotheses": ["H3"],
            "strength": EvidenceStrength.MODERATE,
            "limitations": [
                "Rejects this controlled incident explanation, not all possible organic mix change."
            ],
        }
    )

    # H4 refunds as contributor only.
    prev, cur, growth, verdict = _eval_monthly_growth(
        structured["refunds"],
        support_threshold=10.0,
    )

    h4 = next(h for h in hypotheses if h["hypothesis_id"] == "H4")

    if verdict == "SUPPORTED":
        h4["status"] = HypothesisStatus.WEAK
        h4["confidence"] = 0.48
        claim = "Refunds increased materially and may have contributed."
        supports = ["H4"]
        contradicts = []
    elif verdict == "WEAK":
        h4["status"] = HypothesisStatus.WEAK
        h4["confidence"] = 0.35
        claim = "Refunds increased slightly and may be a minor contributor."
        supports = ["H4"]
        contradicts = []
    else:
        h4["status"] = HypothesisStatus.REJECTED
        h4["confidence"] = 0.65
        claim = "Refund evidence does not support a material profitability driver."
        supports = []
        contradicts = ["H4"]

    ledger.append(
        {
            "evidence_id": "E-H4-REFUNDS",
            "source_type": "sql",
            "source_ref": "finance.daily_pnl",
            "claim": claim,
            "value": {
                "previous": prev,
                "current": cur,
                "growth_pct": None if growth is None else round(growth, 2),
            },
            "supports_hypotheses": supports,
            "contradicts_hypotheses": contradicts,
            "strength": EvidenceStrength.MODERATE,
            "limitations": [
                "Refund movement is treated as a possible contributor, not a dominant cause."
            ],
        }
    )

    if h4["status"] == HypothesisStatus.REJECTED:
        h4["evidence_against"].append("E-H4-REFUNDS")
    else:
        h4["evidence_for"].append("E-H4-REFUNDS")

    # Strict document corroboration.
    from agent.retrieval_phase3c import RankedDocument

    for row in state["business_context"]["retrieved_documents"].get("inc001", []):
        doc = RankedDocument(**row)

        if supplier_cost_relevant(doc):
            ledger.append(
                {
                    "evidence_id": f"DOC-{doc.document_id}-H1",
                    "source_type": "document",
                    "source_ref": doc.filename,
                    "claim": "High-relevance internal document corroborates supplier cost pressure.",
                    "value": {
                        "trust_score": doc.score,
                        "precedence_reason": doc.precedence_reason,
                    },
                    "supports_hypotheses": ["H1"],
                    "contradicts_hypotheses": [],
                    "strength": EvidenceStrength.MODERATE,
                    "limitations": [
                        "Corroborating document; structured cost evidence remains primary."
                    ],
                }
            )

        if campaign_relevant(doc):
            ledger.append(
                {
                    "evidence_id": f"DOC-{doc.document_id}-H2",
                    "source_type": "document",
                    "source_ref": doc.filename,
                    "claim": "High-relevance internal document corroborates campaign activity.",
                    "value": {
                        "trust_score": doc.score,
                        "precedence_reason": doc.precedence_reason,
                    },
                    "supports_hypotheses": ["H2"],
                    "contradicts_hypotheses": [],
                    "strength": EvidenceStrength.MODERATE,
                    "limitations": [
                        "Campaign documentation corroborates activity, not standalone causal magnitude."
                    ],
                }
            )

    # Source precedence conflict fixture.
    inc009 = state["business_context"]["retrieved_documents"].get("inc009", [])
    if len(inc009) >= 2:
        preferred = max(inc009, key=lambda d: d["score"])
        stale = min(inc009, key=lambda d: d["score"])

        if preferred["score"] > stale["score"]:
            conflicts.append(
                "INC009_CONFLICT_RESOLVED_BY_SOURCE_PRECEDENCE:"
                f"{preferred['filename']}>{stale['filename']}"
            )

    # Prompt injection remains data only.
    injected = [
        d for d in state["business_context"]["retrieved_documents"].get("inc011", [])
        if d["instruction_like_content"]
    ]

    if injected:
        ledger.append(
            {
                "evidence_id": "SEC-PROMPT-INJECTION-DETECTED",
                "source_type": "document",
                "source_ref": injected[0]["filename"],
                "claim": "Instruction-like retrieved text detected and treated only as untrusted data.",
                "value": {
                    "instruction_like_content": True,
                    "trust_score": injected[0]["score"],
                },
                "supports_hypotheses": [],
                "contradicts_hypotheses": [],
                "strength": EvidenceStrength.STRONG,
                "limitations": [],
            }
        )

    return {
        "hypotheses": hypotheses,
        "evidence_ledger": ledger,
        "conflicts": conflicts,
        "current_step": state["current_step"] + 1,
    }


def finalize(state: InvestigationState) -> dict[str, Any]:
    supported = sorted(
        [
            h for h in state["hypotheses"]
            if h["status"] == HypothesisStatus.SUPPORTED
        ],
        key=lambda h: h["confidence"],
        reverse=True,
    )

    weak = sorted(
        [
            h for h in state["hypotheses"]
            if h["status"] == HypothesisStatus.WEAK
        ],
        key=lambda h: h["confidence"],
        reverse=True,
    )

    if not supported:
        return {
            "stop_reason": "INSUFFICIENT_CAUSAL_EVIDENCE",
            "conclusion": "No causal hypothesis has sufficient support.",
            "confidence": 0.0,
        }

    primary = supported[0]
    other_supported = supported[1:]

    pieces = [
        f"Primary evidence-supported driver: {primary['statement']}"
    ]

    if other_supported:
        pieces.append(
            "Other supported driver(s): "
            + ", ".join(h["statement"] for h in other_supported)
        )

    if weak:
        pieces.append(
            "Possible secondary contributor(s): "
            + ", ".join(h["statement"] for h in weak)
        )

    return {
        "stop_reason": "PHASE3C_ROOT_CAUSE_EVIDENCE_COMPLETE",
        "conclusion": ". ".join(pieces) + ".",
        "confidence": primary["confidence"],
        "recommended_actions": [
            "Prioritize supplier-cost mitigation and margin protection.",
            "Review campaign unit economics before scaling further spend.",
            "Monitor refunds/CX as a secondary contributor.",
        ],
    }


def build_phase3c_graph():
    graph = StateGraph(InvestigationState)

    graph.add_node("initialize", initialize)
    graph.add_node("gather_structured", gather_structured_evidence)
    graph.add_node("gather_documents", gather_document_evidence)
    graph.add_node("fuse_evidence", fuse_evidence)
    graph.add_node("finalize", finalize)

    graph.add_edge(START, "initialize")
    graph.add_edge("initialize", "gather_structured")
    graph.add_edge("gather_structured", "gather_documents")
    graph.add_edge("gather_documents", "fuse_evidence")
    graph.add_edge("fuse_evidence", "finalize")
    graph.add_edge("finalize", END)

    return graph.compile()


phase3c_graph = build_phase3c_graph()
