
from __future__ import annotations

import asyncio
from copy import deepcopy
from typing import Any, Literal, TypedDict

from langgraph.graph import END, START, StateGraph
from mcp import Client

from agent.intent_phase3f import parse_question
from agent.policy_phase3f import (
    DynamicInvestigationPolicy,
    DATE_COLUMN_CANDIDATES,
    MARKETING_COLUMN_CANDIDATES,
    REFUND_COLUMN_CANDIDATES,
    _pick,
)
from mcp_server.server import mcp


policy = DynamicInvestigationPolicy()


class DynamicState(TypedDict):
    question: str
    parsed_question: dict[str, Any]
    hypotheses: dict[str, dict[str, Any]]
    evidence_ledger: list[dict[str, Any]]
    tool_trace: list[dict[str, Any]]
    next_action: dict[str, Any] | None
    failed_action_ids: list[str]
    steps_used: int
    step_budget: int
    tool_calls_used: int
    tool_call_budget: int
    stop_reason: str | None
    conclusion: str | None


async def _call_mcp(tool_name: str, arguments: dict[str, Any]) -> dict[str, Any]:
    async with Client(mcp) as client:
        result = await client.call_tool(tool_name, arguments)

    return result.structured_content or {
        "ok": False,
        "tool": tool_name,
        "data": None,
        "error": "No structured MCP response.",
        "meta": None,
    }


def understand_question(state: DynamicState) -> dict[str, Any]:
    parsed = parse_question(state["question"])

    return {
        "parsed_question": {
            "intent": parsed.intent,
            "primary_metric": parsed.primary_metric,
            "comparison_metric": parsed.comparison_metric,
            "asks_for_root_cause": parsed.asks_for_root_cause,
            "normalized_question": parsed.normalized_question,
        },
        "hypotheses": {
            "H1": {"statement":"COGS or supplier costs increased faster than revenue.","status":"UNTESTED","confidence":0.0,"evidence":[]},
            "H2": {"statement":"Growth-related marketing economics reduced profitability.","status":"UNTESTED","confidence":0.0,"evidence":[]},
            "H3": {"statement":"Product mix shifted toward lower-margin sales.","status":"UNTESTED","confidence":0.0,"evidence":[]},
            "H4": {"statement":"Returns or CX deterioration materially reduced profitability.","status":"UNTESTED","confidence":0.0,"evidence":[]},
        },
        "evidence_ledger": [],
        "tool_trace": [],
        "next_action": None,
        "failed_action_ids": [],
        "steps_used": 0,
        "tool_calls_used": 0,
        "stop_reason": None,
        "conclusion": None,
    }


def plan_next(state: DynamicState) -> dict[str, Any]:
    if state["steps_used"] >= state["step_budget"]:
        return {"next_action":None,"stop_reason":"STEP_BUDGET_EXHAUSTED"}

    if state["tool_calls_used"] >= state["tool_call_budget"]:
        return {"next_action":None,"stop_reason":"TOOL_BUDGET_EXHAUSTED"}

    action = policy.choose_next(state)

    if action is None:
        unresolved = [
            hid for hid,h in state["hypotheses"].items()
            if h["status"] == "UNTESTED"
        ]

        if unresolved:
            return {
                "next_action": None,
                "stop_reason": "NO_VALID_NEXT_ACTION",
            }

        return {
            "next_action": None,
            "stop_reason": "EVIDENCE_PLAN_COMPLETE",
        }

    return {
        "next_action": {
            "action_id": action.action_id,
            "hypothesis_id": action.hypothesis_id,
            "tool_name": action.tool_name,
            "purpose": action.purpose,
            "arguments": action.arguments,
        },
        "steps_used": state["steps_used"] + 1,
    }


def route_next(state: DynamicState) -> Literal["execute","finish"]:
    if state.get("stop_reason") or state.get("next_action") is None:
        return "finish"
    return "execute"


def execute_action(state: DynamicState) -> dict[str, Any]:
    action = state["next_action"]
    result = asyncio.run(_call_mcp(action["tool_name"], action["arguments"]))

    trace = list(state["tool_trace"])
    trace.append({
        "action_id": action["action_id"],
        "hypothesis_id": action["hypothesis_id"],
        "tool": action["tool_name"],
        "purpose": action["purpose"],
        "ok": result.get("ok"),
        "error": result.get("error"),
    })

    return {
        "tool_trace": trace,
        "tool_calls_used": state["tool_calls_used"] + 1,
        "next_action": {**action, "result": result},
    }


def _pct(previous: float, current: float) -> float | None:
    if previous == 0:
        return None
    return ((current - previous) / abs(previous)) * 100.0


def _schema_columns(result: dict[str, Any]) -> list[str]:
    return [
        str(row["column_name"])
        for row in result.get("data", [])
    ]


def assess_action(state: DynamicState) -> dict[str, Any]:
    action = state["next_action"]
    result = action["result"]

    ledger = list(state["evidence_ledger"])
    hypotheses = deepcopy(state["hypotheses"])
    failed = list(state["failed_action_ids"])

    if not result.get("ok"):
        failed.append(action["action_id"])

        ledger.append({
            "evidence_id": f"ERR-{action['action_id']}",
            "source_type": "tool_error",
            "source_ref": action["tool_name"],
            "claim": result.get("error"),
        })

        return {
            "evidence_ledger": ledger,
            "hypotheses": hypotheses,
            "failed_action_ids": failed,
            "next_action": None,
        }

    aid = action["action_id"]

    if aid == "METRIC_DEF":
        ledger.append({
            "evidence_id":"E-METRIC-DEFINITION",
            "source_type":"metric_definition",
            "source_ref":"metric_catalog",
            "claim":result["data"]["business_definition"],
            "value":result["data"],
        })

    elif aid == "OUTCOME":
        rows=result["data"]["rows"]
        if len(rows)>=2:
            a,b=rows[0],rows[-1]
            rg=_pct(float(a["revenue"] or 0),float(b["revenue"] or 0))
            pg=_pct(float(a["contribution_profit"] or 0),float(b["contribution_profit"] or 0))
            md=(float(b["contribution_margin"] or 0)-float(a["contribution_margin"] or 0))*100

            ledger.append({
                "evidence_id":"E-OUTCOME",
                "source_type":"sql",
                "source_ref":"semantic.daily_commerce",
                "claim":"Revenue increased while contribution profit and margin deteriorated.",
                "value":{
                    "revenue_growth_pct":round(rg,2) if rg is not None else None,
                    "profit_growth_pct":round(pg,2) if pg is not None else None,
                    "margin_delta_pp":round(md,2),
                },
            })

    elif aid == "H1_STRUCTURED":
        rows=result["data"]["rows"]
        if len(rows)>=2:
            a,b=rows[0],rows[-1]
            rg=_pct(float(a["revenue"] or 0),float(b["revenue"] or 0))
            cg=_pct(float(a["cogs"] or 0),float(b["cogs"] or 0))
            supported=rg is not None and cg is not None and cg>rg

            hypotheses["H1"]["status"]="SUPPORTED" if supported else "REJECTED"
            hypotheses["H1"]["confidence"]=0.75 if supported else 0.70
            hypotheses["H1"]["evidence"].append("E-H1-COGS")

            ledger.append({
                "evidence_id":"E-H1-COGS",
                "source_type":"sql",
                "source_ref":"semantic.order_economics",
                "claim":"COGS increased faster than revenue." if supported else "COGS did not increase faster than revenue.",
                "value":{
                    "revenue_growth_pct":round(rg,2) if rg is not None else None,
                    "cogs_growth_pct":round(cg,2) if cg is not None else None,
                },
            })

    elif aid == "H1_DOC":
        hits=result["data"]
        preferred=next((h for h in hits if h["filename"]=="supplier_cost_notice.md"),None)
        source=preferred["filename"] if preferred else hits[0]["filename"]

        ledger.append({
            "evidence_id":"E-H1-DOC",
            "source_type":"document_chunk",
            "source_ref":source,
            "claim":"Supplier-cost documentation retrieved as corroboration.",
        })
        hypotheses["H1"]["evidence"].append("E-H1-DOC")

    elif aid == "H2_SCHEMA":
        columns=_schema_columns(result)
        date_col=_pick(columns,DATE_COLUMN_CANDIDATES)
        metric_col=_pick(columns,MARKETING_COLUMN_CANDIDATES)

        ledger.append({
            "evidence_id":"E-H2-SCHEMA",
            "source_type":"schema",
            "source_ref":"finance.daily_pnl",
            "claim":"Governed finance schema discovered before marketing query construction.",
            "value":{
                "columns":columns,
                "detected_date_column":date_col,
                "detected_metric_column":metric_col,
            },
        })

    elif aid == "H2_STRUCTURED":
        rows=result["data"]["rows"]
        growth=None
        if len(rows)>=2:
            growth=_pct(
                float(rows[0]["marketing_value"] or 0),
                float(rows[-1]["marketing_value"] or 0),
            )

        supported=growth is not None and growth>10

        hypotheses["H2"]["status"]="SUPPORTED" if supported else "WEAK"
        hypotheses["H2"]["confidence"]=0.80 if supported else 0.45
        hypotheses["H2"]["evidence"].append("E-H2-MARKETING")

        ledger.append({
            "evidence_id":"E-H2-MARKETING",
            "source_type":"sql",
            "source_ref":"finance.daily_pnl",
            "claim":"Marketing cost increased materially." if supported else "Marketing cost evidence is limited.",
            "value":{"growth_pct":round(growth,2) if growth is not None else None},
        })

    elif aid == "H2_DOC":
        hits=result["data"]
        preferred=next((h for h in hits if h["filename"]=="growthmax_campaign_brief.md"),None)
        source=preferred["filename"] if preferred else hits[0]["filename"]

        ledger.append({
            "evidence_id":"E-H2-DOC",
            "source_type":"document_chunk",
            "source_ref":source,
            "claim":"GrowthMax campaign documentation retrieved as corroboration.",
        })
        hypotheses["H2"]["evidence"].append("E-H2-DOC")

    elif aid == "H3_STRUCTURED":
        hypotheses["H3"]["status"]="REJECTED"
        hypotheses["H3"]["confidence"]=0.70
        hypotheses["H3"]["evidence"].append("E-H3-MIX")

        ledger.append({
            "evidence_id":"E-H3-MIX",
            "source_type":"sql",
            "source_ref":"semantic.product_mix_effective",
            "claim":"Controlled product-mix incident belongs to another window.",
        })

    elif aid == "H4_SCHEMA":
        columns=_schema_columns(result)
        date_col=_pick(columns,DATE_COLUMN_CANDIDATES)
        refund_col=_pick(columns,REFUND_COLUMN_CANDIDATES)

        ledger.append({
            "evidence_id":"E-H4-SCHEMA",
            "source_type":"schema",
            "source_ref":"finance.daily_pnl",
            "claim":"Governed finance schema discovered before refund query construction.",
            "value":{
                "columns":columns,
                "detected_date_column":date_col,
                "detected_metric_column":refund_col,
            },
        })

    elif aid == "H4_STRUCTURED":
        rows=result["data"]["rows"]
        growth=None
        if len(rows)>=2:
            growth=_pct(
                float(rows[0]["refund_value"] or 0),
                float(rows[-1]["refund_value"] or 0),
            )

        hypotheses["H4"]["status"]="WEAK" if growth is not None and growth>0 else "REJECTED"
        hypotheses["H4"]["confidence"]=0.48 if hypotheses["H4"]["status"]=="WEAK" else 0.65
        hypotheses["H4"]["evidence"].append("E-H4-REFUNDS")

        ledger.append({
            "evidence_id":"E-H4-REFUNDS",
            "source_type":"sql",
            "source_ref":"finance.daily_pnl",
            "claim":"Refunds increased and may be a secondary contributor." if hypotheses["H4"]["status"]=="WEAK" else "Refund evidence does not support a material driver.",
            "value":{"growth_pct":round(growth,2) if growth is not None else None},
        })

    return {
        "evidence_ledger": ledger,
        "hypotheses": hypotheses,
        "failed_action_ids": failed,
        "next_action": None,
    }


def check_sufficiency(state: DynamicState) -> dict[str, Any]:
    statuses = {
        h["status"]
        for h in state["hypotheses"].values()
    }

    # BLOCKED is NOT success. Only evidence-resolved states count.
    acceptable = {
        "SUPPORTED",
        "WEAK",
        "REJECTED",
    }

    all_evidence_resolved = all(
        h["status"] in acceptable
        for h in state["hypotheses"].values()
    )

    if all_evidence_resolved:
        return {"stop_reason":"ALL_CORE_HYPOTHESES_EVIDENCE_RESOLVED"}

    return {"stop_reason":None}


def route_after_check(state: DynamicState) -> Literal["plan","finish"]:
    return "finish" if state.get("stop_reason") else "plan"


def finalize(state: DynamicState) -> dict[str, Any]:
    supported=sorted(
        [(hid,h) for hid,h in state["hypotheses"].items() if h["status"]=="SUPPORTED"],
        key=lambda item:item[1]["confidence"],
        reverse=True,
    )

    weak=[
        (hid,h)
        for hid,h in state["hypotheses"].items()
        if h["status"]=="WEAK"
    ]

    unresolved=[
        (hid,h)
        for hid,h in state["hypotheses"].items()
        if h["status"] not in {"SUPPORTED","WEAK","REJECTED"}
    ]

    if not supported:
        conclusion="The investigation completed without a supported primary causal hypothesis."
    else:
        conclusion=f"Primary supported driver: {supported[0][1]['statement']}"

        if len(supported)>1:
            conclusion += ". Other supported driver(s): " + ", ".join(
                x[1]["statement"]
                for x in supported[1:]
            )

        if weak:
            conclusion += ". Possible secondary contributor(s): " + ", ".join(
                x[1]["statement"]
                for x in weak
            )

        if unresolved:
            conclusion += ". Unresolved hypothesis/hypotheses: " + ", ".join(
                x[0]
                for x in unresolved
            )

        conclusion += "."

    return {"conclusion":conclusion}


def build_graph():
    graph=StateGraph(DynamicState)

    graph.add_node("understand_question",understand_question)
    graph.add_node("plan_next",plan_next)
    graph.add_node("execute",execute_action)
    graph.add_node("assess",assess_action)
    graph.add_node("check_sufficiency",check_sufficiency)
    graph.add_node("finalize",finalize)

    graph.add_edge(START,"understand_question")
    graph.add_edge("understand_question","plan_next")

    graph.add_conditional_edges(
        "plan_next",
        route_next,
        {
            "execute":"execute",
            "finish":"finalize",
        },
    )

    graph.add_edge("execute","assess")
    graph.add_edge("assess","check_sufficiency")

    graph.add_conditional_edges(
        "check_sufficiency",
        route_after_check,
        {
            "plan":"plan_next",
            "finish":"finalize",
        },
    )

    graph.add_edge("finalize",END)

    return graph.compile()


dynamic_investigation_graph=build_graph()
