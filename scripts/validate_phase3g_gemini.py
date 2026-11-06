
from __future__ import annotations

import asyncio
import os
import sys
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]

if str(ROOT) not in sys.path:
    sys.path.insert(0,str(ROOT))

from agent.investigator_phase3g import LLMPlannerInvestigator
from agent.planner_gemini import GeminiPlannerProvider


QUESTION="Why did profit drop even though sales went up?"


async def main():
    if not (
        os.getenv("GEMINI_API_KEY")
        or os.getenv("GOOGLE_API_KEY")
    ):
        print("ERROR: GEMINI_API_KEY or GOOGLE_API_KEY is not set.")
        raise SystemExit(1)

    print("="*104)
    print("OPSLENS PHASE 3G — REAL GEMINI PLANNER INVESTIGATION")
    print("="*104)

    provider=GeminiPlannerProvider()

    investigator=LLMPlannerInvestigator(
        provider=provider,
        step_budget=16,
        tool_call_budget=16,
    )

    result=await investigator.run(QUESTION)

    print("\nModel:",provider.model)

    print("\nPlanner decisions:")
    for i,item in enumerate(result["planner_trace"],start=1):
        print(
            f"  {i}. {item['action_type']} "
            f"{item.get('hypothesis_id') or '-'} "
            f"| confidence={item['confidence']}"
        )
        print(
            f"     rationale: {item['rationale']}"
        )

    print("\nGoverned tool sequence:")
    for item in result["tool_trace"]:
        print(
            f"  - {item['action_id']}: "
            f"{item['tool']} -> ok={item['ok']}"
        )

    print(
        "\nHypotheses:",
        {
            k:v["status"]
            for k,v in result["hypotheses"].items()
        },
    )

    print(
        "Stop reason:",
        result["stop_reason"],
    )

    print(
        "Conclusion:",
        result["conclusion"],
    )

    checks=[]

    def add(name,ok,value):
        checks.append((name,bool(ok),value))

    add(
        "Gemini produced structured planner decisions",
        len(result["planner_trace"]) > 0,
        len(result["planner_trace"]),
    )

    add(
        "All Gemini decisions respected typed contract",
        all(
            d["action_type"]
            in {
                "metric_definition",
                "schema_discovery",
                "structured_test",
                "knowledge_search",
                "stop",
            }
            for d in result["planner_trace"]
        ),
        [
            d["action_type"]
            for d in result["planner_trace"]
        ],
    )

    add(
        "Gemini never authored SQL",
        all(
            not (
                d.get("query_hint")
                and any(
                    token in d["query_hint"].lower()
                    for token in [
                        "select ",
                        "insert ",
                        "update ",
                        "delete ",
                        "drop ",
                        "alter ",
                    ]
                )
            )
            for d in result["planner_trace"]
        ),
        [
            d.get("query_hint")
            for d in result["planner_trace"]
        ],
    )

    add(
        "All governed MCP tool calls succeeded",
        all(
            item["ok"]
            for item in result["tool_trace"]
        ),
        [
            (
                item["action_id"],
                item["ok"],
            )
            for item in result["tool_trace"]
        ],
    )

    add(
        "All core hypotheses evidence-resolved",
        all(
            h["status"]
            in {
                "SUPPORTED",
                "WEAK",
                "REJECTED",
            }
            for h in result["hypotheses"].values()
        ),
        {
            k:v["status"]
            for k,v in result["hypotheses"].items()
        },
    )

    add(
        "Investigation stopped voluntarily",
        result["stop_reason"]=="PLANNER_STOP",
        result["stop_reason"],
    )

    print("\nValidation:")

    passed=0

    for name,ok,value in checks:
        print(
            f"[{'PASS' if ok else 'FAIL'}] "
            f"{name}: {value}"
        )
        passed+=int(ok)

    print(f"\nChecks passed: {passed}/{len(checks)}")

    verdict=(
        "PASS"
        if passed==len(checks)
        else "REVIEW"
    )

    print("VERDICT:",verdict)

    if verdict!="PASS":
        raise SystemExit(1)


if __name__=="__main__":
    asyncio.run(main())
