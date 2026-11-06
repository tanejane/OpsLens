
from __future__ import annotations

import asyncio
from copy import deepcopy
from typing import Any, Literal, TypedDict

from langgraph.graph import END, START, StateGraph
from mcp import Client

from mcp_server.server import mcp


class EvidenceRequest(TypedDict):
    request_id: str
    hypothesis_id: str
    evidence_type: Literal["structured", "knowledge"]
    purpose: str
    query: str
    expected_grain: str | None


class IntegratedState(TypedDict):
    question: str
    requests: list[EvidenceRequest]
    current_request_index: int
    evidence_ledger: list[dict[str, Any]]
    tool_trace: list[dict[str, Any]]
    hypotheses: dict[str, dict[str, Any]]
    stop_reason: str | None
    conclusion: str | None


def initialize(state: IntegratedState) -> dict[str, Any]:
    """
    Phase 3E uses deterministic requests as a baseline.

    Later the LLM planner may propose these requests, but the graph owns the
    allowed tool type, budgets, tool execution, normalization and stop rules.
    """
    requests: list[EvidenceRequest] = [
        {
            "request_id": "R1",
            "hypothesis_id": "H1",
            "evidence_type": "structured",
            "purpose": (
                "Test whether COGS increased faster than revenue in the flagship "
                "profitability deterioration."
            ),
            "query": """
                SELECT
                    DATE_TRUNC(
                        'month',
                        NULLIF(order_purchase_timestamp,'')::timestamp
                    )::date AS business_month,
                    SUM(effective_revenue) AS revenue,
                    SUM(effective_cogs) AS cogs
                FROM semantic.order_economics
                WHERE NULLIF(order_purchase_timestamp,'')::timestamp
                      >= DATE '2018-02-01'
                  AND NULLIF(order_purchase_timestamp,'')::timestamp
                      < DATE '2018-04-01'
                GROUP BY 1
                ORDER BY 1
            """,
            "expected_grain": "one row per business month",
        },
        {
            "request_id": "R2",
            "hypothesis_id": "H1",
            "evidence_type": "knowledge",
            "purpose": (
                "Find internal documentation that corroborates supplier cost "
                "pressure during the flagship incident."
            ),
            "query": (
                "supplier costs increased during March profitability decline"
            ),
            "expected_grain": None,
        },
        {
            "request_id": "R3",
            "hypothesis_id": "H2",
            "evidence_type": "knowledge",
            "purpose": (
                "Find internal documentation about GrowthMax campaign spend "
                "and incentives."
            ),
            "query": "GrowthMax campaign spend incentives",
            "expected_grain": None,
        },
    ]

    return {
        "requests": requests,
        "current_request_index": 0,
        "evidence_ledger": [],
        "tool_trace": [],
        "hypotheses": {
            "H1": {
                "statement": (
                    "COGS or supplier costs increased faster than revenue."
                ),
                "status": "UNTESTED",
                "evidence": [],
            },
            "H2": {
                "statement": (
                    "Growth-related marketing economics reduced profitability."
                ),
                "status": "UNTESTED",
                "evidence": [],
            },
        },
        "stop_reason": None,
        "conclusion": None,
    }


def route_request(
    state: IntegratedState,
) -> Literal["structured", "knowledge", "finish"]:
    idx = state["current_request_index"]

    if idx >= len(state["requests"]):
        return "finish"

    request = state["requests"][idx]

    if request["evidence_type"] == "structured":
        return "structured"

    return "knowledge"


async def _call_mcp(
    tool_name: str,
    arguments: dict[str, Any],
) -> dict[str, Any]:
    async with Client(mcp) as client:
        result = await client.call_tool(
            tool_name,
            arguments,
        )

    return result.structured_content or {
        "ok": False,
        "tool": tool_name,
        "data": None,
        "error": "No structured MCP content returned.",
        "meta": None,
    }


def execute_structured(
    state: IntegratedState,
) -> dict[str, Any]:
    request = state["requests"][state["current_request_index"]]

    result = asyncio.run(
        _call_mcp(
            "run_readonly_sql",
            {
                "query": request["query"],
                "purpose": request["purpose"],
                "expected_grain": request["expected_grain"],
                "max_rows": 20,
            },
        )
    )

    trace = list(state["tool_trace"])
    trace.append(
        {
            "request_id": request["request_id"],
            "hypothesis_id": request["hypothesis_id"],
            "tool": "run_readonly_sql",
            "ok": result.get("ok"),
        }
    )

    ledger = list(state["evidence_ledger"])

    if result.get("ok"):
        rows = result["data"]["rows"]

        ledger.append(
            {
                "evidence_id": "INT-R1-SQL",
                "hypothesis_id": request["hypothesis_id"],
                "source_type": "sql",
                "source_ref": "semantic.order_economics",
                "raw": rows,
                "purpose": request["purpose"],
            }
        )

    return {
        "evidence_ledger": ledger,
        "tool_trace": trace,
        "current_request_index": state["current_request_index"] + 1,
    }


def execute_knowledge(
    state: IntegratedState,
) -> dict[str, Any]:
    request = state["requests"][state["current_request_index"]]

    result = asyncio.run(
        _call_mcp(
            "search_knowledge",
            {
                "query": request["query"],
                "top_k": 3,
            },
        )
    )

    trace = list(state["tool_trace"])
    trace.append(
        {
            "request_id": request["request_id"],
            "hypothesis_id": request["hypothesis_id"],
            "tool": "search_knowledge",
            "ok": result.get("ok"),
        }
    )

    ledger = list(state["evidence_ledger"])

    if result.get("ok"):
        for rank, row in enumerate(result["data"], start=1):
            ledger.append(
                {
                    "evidence_id": (
                        f"INT-{request['request_id']}-DOC-{rank}"
                    ),
                    "hypothesis_id": request["hypothesis_id"],
                    "source_type": "document_chunk",
                    "source_ref": row["filename"],
                    "content": row["content"],
                    "rank": rank,
                    "retrieval_score": row["rerank_score"],
                    "trust_level": row["trust_level"],
                    "purpose": request["purpose"],
                    "injection_flag": row["injection_flag"],
                }
            )

    return {
        "evidence_ledger": ledger,
        "tool_trace": trace,
        "current_request_index": state["current_request_index"] + 1,
    }


def evaluate(
    state: IntegratedState,
) -> dict[str, Any]:
    hypotheses = deepcopy(state["hypotheses"])

    h1_sql = [
        e for e in state["evidence_ledger"]
        if e["hypothesis_id"] == "H1"
        and e["source_type"] == "sql"
    ]

    h1_docs = [
        e for e in state["evidence_ledger"]
        if e["hypothesis_id"] == "H1"
        and e["source_type"] == "document_chunk"
        and "supplier_cost_notice" in e["source_ref"]
    ]

    h2_docs = [
        e for e in state["evidence_ledger"]
        if e["hypothesis_id"] == "H2"
        and e["source_type"] == "document_chunk"
        and "growthmax_campaign_brief" in e["source_ref"]
    ]

    if h1_sql:
        rows = h1_sql[0]["raw"]

        if len(rows) >= 2:
            revenue_prev = float(rows[0]["revenue"] or 0)
            revenue_cur = float(rows[-1]["revenue"] or 0)
            cogs_prev = float(rows[0]["cogs"] or 0)
            cogs_cur = float(rows[-1]["cogs"] or 0)

            revenue_growth = (
                ((revenue_cur - revenue_prev) / abs(revenue_prev)) * 100
                if revenue_prev
                else 0
            )
            cogs_growth = (
                ((cogs_cur - cogs_prev) / abs(cogs_prev)) * 100
                if cogs_prev
                else 0
            )

            if cogs_growth > revenue_growth:
                hypotheses["H1"]["status"] = "SUPPORTED"
                hypotheses["H1"]["evidence"].append(
                    {
                        "type": "structured",
                        "revenue_growth_pct": round(revenue_growth, 2),
                        "cogs_growth_pct": round(cogs_growth, 2),
                    }
                )

    if h1_docs:
        hypotheses["H1"]["evidence"].append(
            {
                "type": "retrieved_document",
                "source": h1_docs[0]["source_ref"],
                "rank": h1_docs[0]["rank"],
            }
        )

    if h2_docs:
        hypotheses["H2"]["status"] = "CORROBORATED"
        hypotheses["H2"]["evidence"].append(
            {
                "type": "retrieved_document",
                "source": h2_docs[0]["source_ref"],
                "rank": h2_docs[0]["rank"],
            }
        )

    return {
        "hypotheses": hypotheses,
        "stop_reason": "INTEGRATED_EVIDENCE_REQUESTS_COMPLETE",
    }


def finalize(
    state: IntegratedState,
) -> dict[str, Any]:
    h1 = state["hypotheses"]["H1"]
    h2 = state["hypotheses"]["H2"]

    return {
        "conclusion": (
            "The integrated investigator successfully used both structured SQL "
            "and hybrid knowledge retrieval through the same MCP boundary. "
            f"H1={h1['status']}; H2={h2['status']}."
        )
    }


def build_graph():
    graph = StateGraph(IntegratedState)

    graph.add_node("initialize", initialize)
    graph.add_node("structured", execute_structured)
    graph.add_node("knowledge", execute_knowledge)
    graph.add_node("evaluate", evaluate)
    graph.add_node("finalize", finalize)

    graph.add_edge(START, "initialize")

    graph.add_conditional_edges(
        "initialize",
        route_request,
        {
            "structured": "structured",
            "knowledge": "knowledge",
            "finish": "evaluate",
        },
    )

    graph.add_conditional_edges(
        "structured",
        route_request,
        {
            "structured": "structured",
            "knowledge": "knowledge",
            "finish": "evaluate",
        },
    )

    graph.add_conditional_edges(
        "knowledge",
        route_request,
        {
            "structured": "structured",
            "knowledge": "knowledge",
            "finish": "evaluate",
        },
    )

    graph.add_edge("evaluate", "finalize")
    graph.add_edge("finalize", END)

    return graph.compile()


integrated_investigation_graph = build_graph()
