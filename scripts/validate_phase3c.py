
from __future__ import annotations
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from agent.graph_phase3c import phase3c_graph
from agent.state import HypothesisStatus


result = phase3c_graph.invoke(
    {
        "question":"Revenue increased but profit fell. Investigate why.",
        "investigation_id":"phase3c-v2-inc001",
        "primary_metric":None,
        "comparison_period":"2018-02 vs 2018-03",
        "business_context":{},
        "plan":[],
        "hypotheses":[],
        "evidence_ledger":[],
        "conflicts":[],
        "missing_evidence":[],
        "current_step":0,
        "step_budget":12,
        "tool_call_budget":12,
        "tool_calls_used":0,
        "stop_reason":None,
        "confidence":0.0,
        "conclusion":None,
        "recommended_actions":[],
    }
)

h={x["hypothesis_id"]:x for x in result["hypotheses"]}
sources=[x["source_ref"] for x in result["evidence_ledger"]]

checks=[
    ("H1 retained and tested",h["H1"]["status"]==HypothesisStatus.SUPPORTED,{"status":h["H1"]["status"],"confidence":h["H1"]["confidence"]}),
    ("H2 tested",h["H2"]["status"]!=HypothesisStatus.UNTESTED,{"status":h["H2"]["status"],"confidence":h["H2"]["confidence"]}),
    ("H3 tested",h["H3"]["status"]==HypothesisStatus.REJECTED,h["H3"]["status"]),
    ("H4 tested",h["H4"]["status"]!=HypothesisStatus.UNTESTED,h["H4"]["status"]),
    ("Irrelevant INC010 note not promoted to H1 evidence","inc010_partial_finance_note.md" not in sources,sources),
    ("Stale forecast not promoted to H1 evidence","stale_finance_forecast.md" not in sources,sources),
    ("Supplier notice retained as corroboration","supplier_cost_notice.md" in sources,sources),
    ("Conflict precedence recorded",any("INC009_CONFLICT_RESOLVED_BY_SOURCE_PRECEDENCE" in x for x in result["conflicts"]),result["conflicts"]),
    ("Prompt injection detected",any(x["evidence_id"]=="SEC-PROMPT-INJECTION-DETECTED" for x in result["evidence_ledger"]),[x["evidence_id"] for x in result["evidence_ledger"]]),
    ("No hidden truth used",all("eval_ground_truth" not in str(x).lower() for x in result["evidence_ledger"]),sources),
]

print("="*96)
print("OPSLENS PHASE 3C v2 — EVIDENCE-CONTINUITY + RETRIEVAL-PRECISION VALIDATION")
print("="*96)

print("\\nHypotheses:")
for x in result["hypotheses"]:
    print(f"- {x['hypothesis_id']}: {x['status']} (confidence={x['confidence']})")

print("\\nEvidence sources:")
for s in sources:
    print(f"- {s}")

print("\\nConclusion:")
print(result["conclusion"])

print("\\nValidation:")
passed=0
for name,ok,value in checks:
    print(f"[{'PASS' if ok else 'FAIL'}] {name}: {value}")
    passed += int(ok)

print(f"\\nChecks passed: {passed}/{len(checks)}")
verdict="PASS" if passed==len(checks) else "REVIEW"
print("VERDICT:",verdict)
if verdict!="PASS":
    raise SystemExit(1)
