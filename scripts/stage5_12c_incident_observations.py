"""Stage 5.12C: request-level incident investigation observations.

Uses existing incident prompts, isolated runtimes and governed MCP.
Observations only: no invented accuracy or mechanism-verification scores.
"""

import asyncio
import json
from datetime import datetime, timezone
from pathlib import Path

from scripts.phase5_1_playground import open_investigation_runtime
from scripts.phase5_3b_incident_eval import PROBE_BY_ID

IDS = ("INC_002", "INC_004", "INC_008", "INC_011")
OUTPUT = Path("reports/stage5_12c_incident_observations.json")


async def run_incident(incident_id):
    probe = PROBE_BY_ID[incident_id]
    client = None

    try:
        runtime, client = await open_investigation_runtime(
            gemini_enabled=False
        )

        result = await asyncio.wait_for(
            runtime.investigate(probe.prompt),
            timeout=180,
        )

        orchestration = result.get("orchestration") or {}
        steps = orchestration.get("trace") or []

        return {
            "incident_id": incident_id,
            "question": probe.prompt,
            "route": result.get("route"),
            "status": result.get("status"),
            "executable": result.get("executable"),
            "causal_claim": result.get("causal_claim"),
            "no_top_level_causal_claim":
                result.get("causal_claim") is False,
            "marketing_followup_present":
                isinstance(result.get("marketing_analysis"), dict),
            "marketing_followup_status":
                (result.get("marketing_analysis") or {}).get("status"),
            "stop_reason": orchestration.get("stop_reason"),
            "steps_used": orchestration.get("steps_used"),
            "tools_used": orchestration.get("tools_used"),
            "trace": [
                {
                    "capability": step.get("capability"),
                    "decision": step.get("decision"),
                    "error_type": step.get("error_type"),
                }
                for step in steps
            ],
            "execution_events": len(
                result.get("execution_trace") or []
            ),
            "limitations_count": len(
                result.get("limitations") or []
            ),
            "runtime_completed": True,
        }

    except Exception as exc:
        return {
            "incident_id": incident_id,
            "question": probe.prompt,
            "runtime_completed": False,
            "error_type": type(exc).__name__,
            "error_message": str(exc)[:250],
        }

    finally:
        if client is not None:
            await client.__aexit__(None, None, None)


async def main():
    records = []

    for incident_id in IDS:
        print(f"\n=== {incident_id} ===", flush=True)

        record = await run_incident(incident_id)
        records.append(record)

        print("Question:", record["question"])
        print("Route:", record.get("route"))
        print("Status:", record.get("status"))
        print("Executable:", record.get("executable"))
        print("Causal claim:", record.get("causal_claim"))
        print("Marketing follow-up:",
              record.get("marketing_followup_status"))
        print("Stop reason:", record.get("stop_reason"))
        print("Steps:", record.get("steps_used"))
        print("Tools:", record.get("tools_used"))
        print("Error:", record.get("error_type"))

        for step in record.get("trace", []):
            print(
                "  ",
                step["capability"],
                "|",
                step["decision"],
                "|",
                step["error_type"] or "",
            )

    report = {
        "contract": "OPSLENS_STAGE5_12C_OBSERVATIONS_V1",
        "mode": "live_request_runtime_no_gemini",
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "cases_attempted": len(records),
        "runtime_completed": sum(
            r["runtime_completed"] for r in records
        ),
        "top_level_noncausal": sum(
            r.get("no_top_level_causal_claim") is True
            for r in records
        ),
        "records": records,
        "limitations": [
            "No independent mechanism verification performed",
            "Routing appropriateness requires case review",
            "Top-level noncausal checks do not audit every nested claim",
            "No general decision-quality accuracy score assigned",
            "These observations do not test API session replay",
        ],
    }

    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(
        json.dumps(report, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )

    print("\n=== STAGE 5.12C SUMMARY ===")
    print("Cases attempted:", report["cases_attempted"])
    print("Runtime completed:", report["runtime_completed"])
    print("Top-level noncausal:", report["top_level_noncausal"])
    print("Decision quality: PENDING CASE REVIEW")
    print("Report:", OUTPUT)


if __name__ == "__main__":
    asyncio.run(main())
