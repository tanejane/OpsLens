from __future__ import annotations
import sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0,str(ROOT))

from agent.graph_phase3b import phase3b_graph
from agent.state import HypothesisStatus

result=phase3b_graph.invoke({
    "question":"Revenue increased but profit fell. Investigate why.",
    "investigation_id":"phase3b-v2-inc001",
    "primary_metric":None,"comparison_period":"2018-02 vs 2018-03","business_context":{},
    "plan":[],"hypotheses":[],"evidence_ledger":[],"conflicts":[],"missing_evidence":[],
    "current_step":0,"step_budget":6,"tool_call_budget":4,"tool_calls_used":0,
    "stop_reason":None,"confidence":0.0,"conclusion":None,"recommended_actions":[]
})

h1=next(h for h in result["hypotheses"] if h["hypothesis_id"]=="H1")
h2=next(h for h in result["hypotheses"] if h["hypothesis_id"]=="H2")

checks=[
    ("Outcome pattern confirmed separately",result["business_context"].get("outcome_confirmed") is True,result["business_context"].get("outcome_confirmed")),
    ("H1 supported by COGS evidence",h1["status"]==HypothesisStatus.SUPPORTED,{"status":h1["status"],"confidence":h1["confidence"]}),
    ("H2 remains untested without marketing evidence",h2["status"]==HypothesisStatus.UNTESTED,{"status":h2["status"],"confidence":h2["confidence"]}),
    ("Final conclusion points to H1","COGS or supplier costs increased faster than revenue" in result["conclusion"],result["conclusion"]),
    ("Conclusion does not falsely attribute marketing","Growth-related marketing economics reduced profitability" not in result["conclusion"],result["conclusion"]),
    ("No hidden truth used",all("eval_ground_truth" not in str(e).lower() for e in result["evidence_ledger"]),[e["source_ref"] for e in result["evidence_ledger"]])
]

print("="*92)
print("OPSLENS PHASE 3B v2 — CAUSAL-SEPARATION VALIDATION")
print("="*92)
print("\nEvidence ledger:")
for e in result["evidence_ledger"]:
    print(f"- {e['evidence_id']}: {e['claim']} | {e['value']}")
print("\nHypotheses:")
for h in result["hypotheses"]:
    print(f"- {h['hypothesis_id']}: {h['status']} (confidence={h['confidence']})")
print("\nConclusion:")
print(result["conclusion"])
print("\nValidation:")
passed=0
for name,ok,value in checks:
    print(f"[{'PASS' if ok else 'FAIL'}] {name}: {value}")
    passed += int(ok)
print(f"\nChecks passed: {passed}/{len(checks)}")
verdict="PASS" if passed==len(checks) else "REVIEW"
print("VERDICT:",verdict)
if verdict!="PASS":
    raise SystemExit(1)
