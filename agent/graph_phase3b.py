from __future__ import annotations
import asyncio
from copy import deepcopy
from langgraph.graph import START, END, StateGraph
from agent.evidence import assess_cogs_vs_revenue, assess_profitability_pattern
from agent.mcp_bridge import run_sql_evidence
from agent.planner import DeterministicBaselinePlanner
from agent.state import HypothesisStatus, InvestigationState

planner = DeterministicBaselinePlanner()

def initialize(state: InvestigationState):
    return {
        "primary_metric":"contribution_profit",
        "hypotheses":[
            {"hypothesis_id":"H1","statement":"COGS or supplier costs increased faster than revenue.","status":HypothesisStatus.UNTESTED,"rationale":"Higher unit costs compress profitability.","evidence_for":[],"evidence_against":[],"confidence":0.0,"next_test":"Compare effective revenue and COGS."},
            {"hypothesis_id":"H2","statement":"Growth-related marketing economics reduced profitability.","status":HypothesisStatus.UNTESTED,"rationale":"Growth can be unprofitable when acquisition costs rise.","evidence_for":[],"evidence_against":[],"confidence":0.0,"next_test":"Inspect campaign spend and incentives."},
            {"hypothesis_id":"H3","statement":"Product mix shifted toward lower-margin sales.","status":HypothesisStatus.UNTESTED,"rationale":"Mix can dilute margin.","evidence_for":[],"evidence_against":[],"confidence":0.0,"next_test":"Inspect mix evidence."},
            {"hypothesis_id":"H4","statement":"Returns or CX deterioration materially reduced profitability.","status":HypothesisStatus.UNTESTED,"rationale":"Refunds/CX can erode profit.","evidence_for":[],"evidence_against":[],"confidence":0.0,"next_test":"Inspect CX evidence."}
        ],
        "evidence_ledger":[],
        "conflicts":[],
        "missing_evidence":[],
        "tool_calls_used":0,
        "current_step":0,
        "stop_reason":None,
        "confidence":0.0,
        "conclusion":None,
        "recommended_actions":[],
        "business_context":{"planner_provider":"DeterministicBaselinePlanner","runtime_boundary":"OpsLens MCP only","outcome_confirmed":False}
    }

def plan_tests(state: InvestigationState):
    tests = planner.plan_flagship_profitability_tests(state["question"])
    return {
        "plan":[{"step_id":t.test_id,"purpose":t.purpose,"tool_name":"run_readonly_sql","status":"PENDING","expected_grain":t.expected_grain,"hypothesis_ids":[] if t.hypothesis_id is None else [t.hypothesis_id]} for t in tests],
        "business_context":{**state["business_context"],"planned_tests":[{"test_id":t.test_id,"hypothesis_id":t.hypothesis_id,"purpose":t.purpose,"expected_grain":t.expected_grain,"query":t.query} for t in tests]}
    }

def execute_tests(state: InvestigationState):
    results=[]
    for test in state["business_context"]["planned_tests"]:
        if state["tool_calls_used"] + len(results) >= state["tool_call_budget"]:
            break
        result = asyncio.run(run_sql_evidence(test["query"], test["purpose"], test["expected_grain"], 20))
        results.append({"test_id":test["test_id"],"hypothesis_id":test["hypothesis_id"],"result":result})
    return {"business_context":{**state["business_context"],"tool_results":results},"tool_calls_used":state["tool_calls_used"]+len(results),"current_step":state["current_step"]+1}

def evaluate_evidence(state: InvestigationState):
    hypotheses=deepcopy(state["hypotheses"])
    ledger=list(state["evidence_ledger"])
    ctx=dict(state["business_context"])

    for item in state["business_context"]["tool_results"]:
        if item["test_id"]=="OUTCOME":
            a=assess_profitability_pattern(item["result"])
            ledger.append(a.evidence_item)
            ctx["outcome_confirmed"] = a.hypothesis_status == HypothesisStatus.SUPPORTED
            continue

        if item["hypothesis_id"]=="H1":
            a=assess_cogs_vs_revenue(item["result"])
        else:
            continue

        ledger.append(a.evidence_item)
        for h in hypotheses:
            if h["hypothesis_id"]==item["hypothesis_id"]:
                h["status"]=a.hypothesis_status
                h["confidence"]=a.confidence
                eid=a.evidence_item["evidence_id"]
                if a.hypothesis_status==HypothesisStatus.REJECTED:
                    h["evidence_against"].append(eid)
                else:
                    h["evidence_for"].append(eid)

    return {"hypotheses":hypotheses,"evidence_ledger":ledger,"business_context":ctx}

def decide_stop(state: InvestigationState):
    if state["conflicts"]:
        return {"stop_reason":None,"missing_evidence":["Resolve conflicting evidence before finalizing."]}
    if state["business_context"].get("outcome_confirmed") and any(h["status"]==HypothesisStatus.SUPPORTED for h in state["hypotheses"]):
        return {"stop_reason":"PHASE3B_EVIDENCE_COMPLETE"}
    if state["tool_calls_used"] >= state["tool_call_budget"]:
        return {"stop_reason":"TOOL_BUDGET_EXHAUSTED"}
    return {"stop_reason":"PHASE3B_TEST_SET_COMPLETE"}

def finalize(state: InvestigationState):
    supported=sorted([h for h in state["hypotheses"] if h["status"]==HypothesisStatus.SUPPORTED], key=lambda h:h["confidence"], reverse=True)
    if not state["business_context"].get("outcome_confirmed"):
        return {"conclusion":"The reported profitability deterioration was not confirmed.","confidence":0.0}
    if not supported:
        return {"conclusion":"The profitability deterioration is confirmed, but no causal hypothesis has sufficient support yet.","confidence":0.0}
    top=supported[0]
    return {"conclusion":f"The profitability deterioration is confirmed. Initial causal evidence supports: {top['statement']} This remains a partial root-cause result until the remaining hypotheses are tested.","confidence":top["confidence"]}

def build():
    g=StateGraph(InvestigationState)
    for n,f in [("initialize",initialize),("plan_tests",plan_tests),("execute_tests",execute_tests),("evaluate_evidence",evaluate_evidence),("decide_stop",decide_stop),("finalize",finalize)]:
        g.add_node(n,f)
    g.add_edge(START,"initialize"); g.add_edge("initialize","plan_tests"); g.add_edge("plan_tests","execute_tests"); g.add_edge("execute_tests","evaluate_evidence"); g.add_edge("evaluate_evidence","decide_stop"); g.add_edge("decide_stop","finalize"); g.add_edge("finalize",END)
    return g.compile()

phase3b_graph=build()
