
from __future__ import annotations

import sys
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]

if str(ROOT) not in sys.path:
    sys.path.insert(0,str(ROOT))

from agent.graph_phase3f import dynamic_investigation_graph


QUESTIONS=[
    "Why did profit drop even though sales went up?",
    "Sales increased but profitability got worse. What caused it?",
    "为什么营收上升但是利润下降？",
]


def run_case(question):
    return dynamic_investigation_graph.invoke({
        "question":question,
        "parsed_question":{},
        "hypotheses":{},
        "evidence_ledger":[],
        "tool_trace":[],
        "next_action":None,
        "failed_action_ids":[],
        "steps_used":0,
        "step_budget":16,
        "tool_calls_used":0,
        "tool_call_budget":16,
        "stop_reason":None,
        "conclusion":None,
    })


results=[run_case(q) for q in QUESTIONS]
first=results[0]


print("="*104)
print("OPSLENS PHASE 3F v3 — FULLY SCHEMA-ADAPTIVE DYNAMIC LOOP VALIDATION")
print("="*104)

for q,r in zip(QUESTIONS,results):
    print("\\nQuestion:",q)
    print("Tool sequence:")
    for x in r["tool_trace"]:
        print(
            f"  - {x['action_id']}: "
            f"{x['tool']} -> ok={x['ok']}"
            + (f" | error={x['error']}" if not x["ok"] else "")
        )

    print(
        "Hypotheses:",
        {
            k:v["status"]
            for k,v in r["hypotheses"].items()
        },
    )
    print("Stop reason:",r["stop_reason"])
    print("Conclusion:",r["conclusion"])


ids=[
    x["action_id"]
    for x in first["tool_trace"]
]

all_ok=all(
    item["ok"]
    for item in first["tool_trace"]
)

resolved_statuses={
    "SUPPORTED",
    "WEAK",
    "REJECTED",
}

checks=[
    (
        "H2 schema discovery happened before H2 SQL",
        "H2_SCHEMA" in ids
        and "H2_STRUCTURED" in ids
        and ids.index("H2_SCHEMA") < ids.index("H2_STRUCTURED"),
        ids,
    ),
    (
        "H4 schema discovery happened before H4 SQL",
        "H4_SCHEMA" in ids
        and "H4_STRUCTURED" in ids
        and ids.index("H4_SCHEMA") < ids.index("H4_STRUCTURED"),
        ids,
    ),
    (
        "All dynamic tool calls succeeded",
        all_ok,
        [
            {
                "action":x["action_id"],
                "ok":x["ok"],
                "error":x["error"],
            }
            for x in first["tool_trace"]
        ],
    ),
    (
        "No hypothesis is BLOCKED or UNTESTED",
        all(
            h["status"] in resolved_statuses
            for h in first["hypotheses"].values()
        ),
        {
            k:v["status"]
            for k,v in first["hypotheses"].items()
        },
    ),
    (
        "Loop stopped on evidence resolution, not budget exhaustion",
        first["stop_reason"]=="ALL_CORE_HYPOTHESES_EVIDENCE_RESOLVED",
        first["stop_reason"],
    ),
    (
        "Metric, schema, SQL and retrieval tools were all used",
        {
            "get_metric_definition",
            "describe_relation",
            "run_readonly_sql",
            "search_knowledge",
        }.issubset(
            {
                x["tool"]
                for x in first["tool_trace"]
            }
        ),
        sorted(
            {
                x["tool"]
                for x in first["tool_trace"]
            }
        ),
    ),
    (
        "English paraphrase still routes",
        results[1]["parsed_question"]["intent"]
        =="root_cause_investigation",
        results[1]["parsed_question"],
    ),
    (
        "Chinese question still routes",
        results[2]["parsed_question"]["intent"]
        =="root_cause_investigation",
        results[2]["parsed_question"],
    ),
]


print("\\nValidation:")

passed=0

for name,ok,value in checks:
    print(
        f"[{'PASS' if ok else 'FAIL'}] "
        f"{name}: {value}"
    )
    passed += int(ok)


print(f"\\nChecks passed: {passed}/{len(checks)}")

verdict="PASS" if passed==len(checks) else "REVIEW"

print("VERDICT:",verdict)

if verdict!="PASS":
    raise SystemExit(1)
