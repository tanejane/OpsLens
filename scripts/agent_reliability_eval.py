
"""OpsLens agent reliability baseline.

Evaluates an existing saved canonical investigation.
No agent, model, MCP, or database execution occurs.
"""

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path


def as_dict(value):
    return value if isinstance(value, dict) else {}


def as_list(value):
    return value if isinstance(value, list) else []


def evaluate(record):
    canonical = as_dict(record.get("canonical_result", record))
    payload = as_dict(canonical.get("payload"))
    trace = as_dict(payload.get("agent_trace_v2"))

    events = as_list(trace.get("events"))
    stops = as_list(trace.get("stop_conditions"))
    raw_calls = as_list(payload.get("execution_trace"))
    adaptive = as_dict(payload.get("adaptive"))
    orchestration = as_dict(payload.get("orchestration"))

    checks = []

    def check(name, passed, detail):
        checks.append({
            "name": name,
            "passed": bool(passed),
            "detail": detail,
        })

    check(
        "Canonical contract",
        canonical.get("schema_version") == "opslens.investigation.v1",
        "Versioned investigation record",
    )

    check(
        "Trace V2 contract",
        trace.get("schema_version") == "opslens.agent_trace.v2",
        "Versioned execution trace",
    )

    check(
        "Ordering honesty",
        trace.get("global_sequence_verified") is False
        and trace.get("ordering") == "SOURCE_LOCAL_ONLY",
        "No fabricated global event chronology",
    )

    ids = [event.get("id") for event in events if isinstance(event, dict)]

    check(
        "Unique source-local event IDs",
        len(ids) == len(set(ids))
        and all(isinstance(item, str) and item for item in ids),
        f"{len(ids)} event identifiers inspected",
    )

    projected_calls = [
        event for event in events
        if isinstance(event, dict)
        and event.get("stage") == "tool_execution"
        and event.get("source") == "execution"
    ]

    call_match = (
        len(projected_calls) == len(raw_calls)
        and all(
            event.get("id") == f"execution:{index}"
            and event.get("source_index") == index
            and event.get("tool") == as_dict(raw_calls[index]).get("tool")
            and event.get("outcome") == as_dict(raw_calls[index]).get("outcome")
            for index, event in enumerate(projected_calls)
        )
    )

    check(
        "Tool-call trace consistency",
        call_match,
        f"{len(projected_calls)} projected / {len(raw_calls)} recorded",
    )

    forbidden = {
        "arguments", "query", "response",
        "api_key", "password", "access_token",
    }

    projection = json.dumps(trace, ensure_ascii=False).lower()

    safe_fields = all(
        not forbidden.intersection(event)
        for event in events + stops
        if isinstance(event, dict)
    )

    check(
        "Projection excludes raw execution fields",
        safe_fields and bool(trace.get("raw_execution_excluded")),
        "Checks field structure; not a complete secret-leak audit",
    )

    expected_stops = {
        ("orchestration", orchestration.get("stop_reason")),
        ("adaptive", adaptive.get("stop_reason")),
    }
    expected_stops = {
        item for item in expected_stops if isinstance(item[1], str) and item[1]
    }

    actual_stops = {
        (event.get("source"), event.get("reason"))
        for event in stops
        if isinstance(event, dict)
    }

    check(
        "Stopping reason preservation",
        expected_stops.issubset(actual_stops),
        f"{len(expected_stops)} expected coordinator stop conditions",
    )

    measured = as_dict(payload.get("metric_results"))
    premises = as_dict(payload.get("premise"))

    has_measurements = bool(measured) or bool(payload.get("evidence"))

    check(
        "Financial evidence retained",
        has_measurements,
        "This baseline expects a measured financial investigation",
    )

    check(
        "No causal conclusion claimed",
        payload.get("causal_claim") is False,
        "Descriptive accounting is not causal identification",
    )

    check(
        "Premise evaluation recorded",
        isinstance(premises.get("divergence_confirmed"), bool),
        "Recorded positive or negative financial premise",
    )

    check(
        "Conditional finance stages preserved",
        len(as_list(adaptive.get("trace"))) > 0,
        "Recorded domain-specific investigation steps",
    )

    passed = sum(item["passed"] for item in checks)

    return {
        "suite": "opslens.agent_reliability.baseline.v1",
        "evaluated_at": datetime.now(timezone.utc).isoformat(),
        "scope": "ONE_SAVED_FINANCIAL_INVESTIGATION",
        "execution_mode": "OFFLINE_SAVED_RECORD",
        "checks_passed": passed,
        "checks_total": len(checks),
        "pass_rate": round(passed / len(checks), 4),
        "recorded_tool_calls": len(raw_calls),
        "projected_events": len(events),
        "recorded_stop_conditions": len(stops),
        "checks": checks,
        "limitations": [
            "Does not measure routing accuracy across questions.",
            "Does not prove absence of calls during HTTP replay.",
            "Does not test live SQL permissions or database correctness.",
            "Does not test recovery, timeouts or budget exhaustion.",
            "Does not establish general agent reliability.",
        ],
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("record", type=Path)
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("reports/agent_reliability_baseline.json"),
    )
    args = parser.parse_args()

    record = json.loads(args.record.read_text(encoding="utf-8-sig"))
    result = evaluate(record)

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(result, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )

    for item in result["checks"]:
        status = "PASS" if item["passed"] else "FAIL"
        print(f"[{status}] {item['name']}: {item['detail']}")

    print(
        f"\nBaseline: {result['checks_passed']}/"
        f"{result['checks_total']} checks passed"
    )
    print(f"Report: {args.output}")

    raise SystemExit(0 if result["checks_passed"] == result["checks_total"] else 1)


if __name__ == "__main__":
    main()
