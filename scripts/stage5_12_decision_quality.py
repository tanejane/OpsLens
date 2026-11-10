"""Stage 5.12A: Request-level agent decision-quality evaluation.

Three independent governed MCP investigations.
Gemini disabled. Read-only execution.
"""

import asyncio
import json
from datetime import datetime, timezone
from pathlib import Path

from scripts.phase5_1_playground import open_investigation_runtime

OUTPUT = Path("reports/stage5_12_decision_quality.json")

CASES = [
    {
        "id": "A_FINANCE_FOLLOWUP",
        "question": (
            "Revenue grew but contribution profit fell from February "
            "2018 to March 2018. Investigate the accounting pressures "
            "and state what needs independent validation."
        ),
    },
    {
        "id": "B_DELIVERY_ONLY",
        "question": "What was the late delivery rate in June 2018?",
    },
    {
        "id": "C_UNSUPPORTED_CAUSAL",
        "question": (
            "Did delivery delays cause poor reviews and profit decline "
            "between February 2018 and March 2018?"
        ),
    },
]


def assess(case_id, result):
    marketing = result.get("marketing_analysis")
    orchestration = result.get("orchestration") or {}
    steps = orchestration.get("trace") or []

    marketing_actions = [
        step for step in steps
        if step.get("capability") == "marketing_campaign_composition"
    ]

    noncausal = result.get("causal_claim") is False

    if case_id == "A_FINANCE_FOLLOWUP":
        decision_ok = (
            isinstance(marketing, dict)
            and marketing.get("status") == "DESCRIPTIVE_RECONCILED"
            and marketing.get("independent_mechanism_verified") is False
            and any(
                s.get("decision") == "VALIDATED"
                for s in marketing_actions
            )
            and orchestration.get("stop_reason")
                == "MARKETING_FOLLOWUP_COMPLETED"
        )

        handling_ok = (
            result.get("route") == "investigation"
            and result.get("status") == "EVIDENCE_RANKED_NOT_CAUSAL"
            and decision_ok
        )

    elif case_id == "B_DELIVERY_ONLY":
        decision_ok = (
            len(marketing_actions) == 0
            and marketing is None
        )

        handling_ok = (
            result.get("route") == "delivery_operations"
            and result.get("executable") is True
            and result.get("status") == "MEASURED_WITH_SCOPE_LIMITS"
        )

    else:
        decision_ok = (
            len(marketing_actions) == 0
            and marketing is None
        )

        handling_ok = (
            result.get("executable") is False
            and result.get("status") == "NEEDS_CLARIFICATION"
        )

    return {
        "decision_selection_pass": bool(decision_ok),
        "question_handling_pass": bool(handling_ok),
        "noncausal_safety_pass": bool(noncausal),
        "overall_pass": bool(
            decision_ok and handling_ok and noncausal
        ),
    }


async def run_case(case):
    client = None

    try:
        runtime, client = await open_investigation_runtime(
            gemini_enabled=False
        )

        result = await asyncio.wait_for(
            runtime.investigate(case["question"]),
            timeout=180,
        )

        orchestration = result.get("orchestration") or {}

        observation = {
            "id": case["id"],
            "question": case["question"],
            "route": result.get("route"),
            "status": result.get("status"),
            "executable": result.get("executable"),
            "causal_claim": result.get("causal_claim"),
            "marketing_status": (
                (result.get("marketing_analysis") or {}).get("status")
            ),
            "stop_reason": orchestration.get("stop_reason"),
            "steps_used": orchestration.get("steps_used"),
            "tools_used": orchestration.get("tools_used"),
            "trace": [
                {
                    "capability": step.get("capability"),
                    "decision": step.get("decision"),
                    "error_type": step.get("error_type"),
                }
                for step in orchestration.get("trace", [])
            ],
        }

        observation["checks"] = assess(case["id"], result)
        return observation

    except Exception as exc:
        return {
            "id": case["id"],
            "error_type": type(exc).__name__,
            "error_message": str(exc)[:200],
            "checks": {
                "decision_selection_pass": False,
                "question_handling_pass": False,
                "noncausal_safety_pass": False,
                "overall_pass": False,
            },
        }

    finally:
        if client is not None:
            await client.__aexit__(None, None, None)


async def main():
    observations = []

    for case in CASES:
        print(f"\n=== {case['id']} ===", flush=True)

        observation = await run_case(case)
        observations.append(observation)

        print("Route:", observation.get("route"))
        print("Status:", observation.get("status"))
        print("Stop:", observation.get("stop_reason"))
        print("Steps:", observation.get("steps_used"))
        print("Tools:", observation.get("tools_used"))
        print("Error:", observation.get("error_type"))
        print("Checks:", observation["checks"])

    score_names = (
        "decision_selection_pass",
        "question_handling_pass",
        "noncausal_safety_pass",
        "overall_pass",
    )

    scores = {
        name: sum(
            int(observation["checks"][name])
            for observation in observations
        )
        for name in score_names
    }

    report = {
        "contract": "OPSLENS_STAGE5_12_DECISION_PILOT_V1",
        "mode": "live_request_runtime_no_gemini",
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "cases_attempted": len(observations),
        "scores": scores,
        "observations": observations,
        "limitations": [
            "Only three selected scenarios.",
            "No independent mechanism verification.",
            "Not a general agent accuracy benchmark.",
            "No HTTP session or replay testing.",
        ],
    }

    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(
        json.dumps(report, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )

    print("\n=== STAGE 5.12A SUMMARY ===")

    for name, count in scores.items():
        print(f"{name}: {count}/{len(observations)}")

    print("Report:", OUTPUT)


if __name__ == "__main__":
    asyncio.run(main())
