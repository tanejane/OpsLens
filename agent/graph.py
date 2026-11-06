
from __future__ import annotations

from copy import deepcopy
from typing import Literal

from langgraph.graph import END, START, StateGraph

from agent.state import (
    EvidenceItem,
    EvidenceStrength,
    Hypothesis,
    HypothesisStatus,
    InvestigationPlanItem,
    InvestigationState,
)


def _initial_hypotheses() -> list[Hypothesis]:
    """
    Deterministic starter hypotheses for the flagship profitability question.

    In the next phase, these will be generated/refined by an LLM planner.
    For Phase 3A we intentionally keep them deterministic so the graph control
    behavior can be tested independently from model quality.
    """
    return [
        {
            "hypothesis_id": "H1",
            "statement": "COGS or supplier costs increased faster than revenue.",
            "status": HypothesisStatus.UNTESTED,
            "rationale": (
                "Revenue growth can still reduce contribution profit if unit "
                "economics deteriorate."
            ),
            "evidence_for": [],
            "evidence_against": [],
            "confidence": 0.0,
            "next_test": "Compare revenue, COGS, and contribution margin over time.",
        },
        {
            "hypothesis_id": "H2",
            "statement": "Marketing spend or campaign incentives increased materially.",
            "status": HypothesisStatus.UNTESTED,
            "rationale": (
                "Growth can be unprofitable when acquisition and incentive costs "
                "rise faster than incremental gross profit."
            ),
            "evidence_for": [],
            "evidence_against": [],
            "confidence": 0.0,
            "next_test": "Compare campaign spend and effective marketing economics.",
        },
        {
            "hypothesis_id": "H3",
            "statement": "Product mix shifted toward lower-margin sales.",
            "status": HypothesisStatus.UNTESTED,
            "rationale": (
                "Revenue can rise while blended margin falls if the sales mix shifts."
            ),
            "evidence_for": [],
            "evidence_against": [],
            "confidence": 0.0,
            "next_test": "Inspect effective product mix economics.",
        },
        {
            "hypothesis_id": "H4",
            "statement": "Refunds or customer-experience deterioration reduced profitability.",
            "status": HypothesisStatus.UNTESTED,
            "rationale": (
                "Higher returns, refunds, and service failures can erode otherwise "
                "healthy revenue growth."
            ),
            "evidence_for": [],
            "evidence_against": [],
            "confidence": 0.0,
            "next_test": "Inspect returns, effective reviews, and delivery deterioration.",
        },
    ]


def initialize_investigation(state: InvestigationState) -> dict:
    return {
        "primary_metric": "contribution_profit",
        "business_context": {
            "analysis_mode": "root_cause_investigation",
            "causality_rule": (
                "Correlation or metric movement alone is not proof of causality."
            ),
            "data_boundary": (
                "Use canonical/semantic runtime sources only. Hidden eval truth "
                "must never enter the investigation."
            ),
        },
        "plan": [],
        "hypotheses": _initial_hypotheses(),
        "evidence_ledger": [],
        "conflicts": [],
        "missing_evidence": [],
        "current_step": 0,
        "stop_reason": None,
        "confidence": 0.0,
        "conclusion": None,
        "recommended_actions": [],
    }


def build_plan(state: InvestigationState) -> dict:
    plan: list[InvestigationPlanItem] = [
        {
            "step_id": "P1",
            "purpose": (
                "Confirm the reported pattern in effective revenue, contribution "
                "profit, and contribution margin."
            ),
            "tool_name": "run_readonly_sql",
            "status": "PENDING",
            "expected_grain": "one row per business month",
            "hypothesis_ids": ["H1", "H2", "H3", "H4"],
        },
        {
            "step_id": "P2",
            "purpose": "Test whether COGS/supplier economics deteriorated.",
            "tool_name": "run_readonly_sql",
            "status": "PENDING",
            "expected_grain": "month or affected product segment",
            "hypothesis_ids": ["H1"],
        },
        {
            "step_id": "P3",
            "purpose": "Test whether marketing economics became less profitable.",
            "tool_name": "run_readonly_sql",
            "status": "PENDING",
            "expected_grain": "campaign or business month",
            "hypothesis_ids": ["H2"],
        },
        {
            "step_id": "P4",
            "purpose": "Test whether product mix diluted blended margin.",
            "tool_name": "run_readonly_sql",
            "status": "PENDING",
            "expected_grain": "category or product segment",
            "hypothesis_ids": ["H3"],
        },
        {
            "step_id": "P5",
            "purpose": "Test returns/CX deterioration as an alternate explanation.",
            "tool_name": "run_readonly_sql",
            "status": "PENDING",
            "expected_grain": "month, seller, or order",
            "hypothesis_ids": ["H4"],
        },
    ]

    return {"plan": plan}


def select_next_hypothesis(state: InvestigationState) -> dict:
    hypotheses = deepcopy(state["hypotheses"])

    for hypothesis in hypotheses:
        if hypothesis["status"] == HypothesisStatus.UNTESTED:
            hypothesis["status"] = HypothesisStatus.TESTING
            return {"hypotheses": hypotheses}

    return {}


def evidence_sufficiency(state: InvestigationState) -> dict:
    supported = [
        h for h in state["hypotheses"]
        if h["status"] == HypothesisStatus.SUPPORTED
    ]
    conflicting = [
        h for h in state["hypotheses"]
        if h["status"] == HypothesisStatus.CONFLICTING
    ]

    # Phase 3A deliberately uses explicit deterministic stop rules.
    # Later LLM reasoning may propose hypotheses, but application logic controls
    # whether the investigation is allowed to stop.
    if conflicting:
        return {
            "stop_reason": None,
            "missing_evidence": [
                "Resolve conflicting evidence before final conclusion."
            ],
        }

    if len(supported) >= 1 and len(state["evidence_ledger"]) >= 2:
        return {
            "stop_reason": "SUFFICIENT_EVIDENCE",
        }

    if state["tool_calls_used"] >= state["tool_call_budget"]:
        return {
            "stop_reason": "TOOL_BUDGET_EXHAUSTED",
        }

    if state["current_step"] >= state["step_budget"]:
        return {
            "stop_reason": "STEP_BUDGET_EXHAUSTED",
        }

    return {
        "stop_reason": None,
    }


def finalize(state: InvestigationState) -> dict:
    supported = [
        h for h in state["hypotheses"]
        if h["status"] == HypothesisStatus.SUPPORTED
    ]

    if supported:
        ranked = sorted(
            supported,
            key=lambda h: h["confidence"],
            reverse=True,
        )
        conclusion = (
            "Current evidence supports: "
            + "; ".join(h["statement"] for h in ranked)
        )
        confidence = max(h["confidence"] for h in ranked)
    else:
        conclusion = (
            "No hypothesis has sufficient support yet. "
            "The investigation should remain uncertain."
        )
        confidence = 0.0

    return {
        "conclusion": conclusion,
        "confidence": confidence,
    }


def route_after_sufficiency(
    state: InvestigationState,
) -> Literal["finalize", "continue"]:
    if state.get("stop_reason"):
        return "finalize"
    return "continue"


def continue_stub(state: InvestigationState) -> dict:
    """
    Phase 3A stops short of model/tool execution.

    We increment application-owned budgets so graph looping and stop behavior
    can be validated before wiring the MCP client and LLM in Phase 3B.
    """
    return {
        "current_step": state["current_step"] + 1,
        "tool_calls_used": state["tool_calls_used"] + 1,
    }


def build_graph():
    graph = StateGraph(InvestigationState)

    graph.add_node("initialize", initialize_investigation)
    graph.add_node("plan", build_plan)
    graph.add_node("select_hypothesis", select_next_hypothesis)
    graph.add_node("check_evidence", evidence_sufficiency)
    graph.add_node("continue_stub", continue_stub)
    graph.add_node("finalize", finalize)

    graph.add_edge(START, "initialize")
    graph.add_edge("initialize", "plan")
    graph.add_edge("plan", "select_hypothesis")
    graph.add_edge("select_hypothesis", "check_evidence")

    graph.add_conditional_edges(
        "check_evidence",
        route_after_sufficiency,
        {
            "finalize": "finalize",
            "continue": "continue_stub",
        },
    )

    graph.add_edge("continue_stub", "check_evidence")
    graph.add_edge("finalize", END)

    return graph.compile()


investigation_graph = build_graph()
