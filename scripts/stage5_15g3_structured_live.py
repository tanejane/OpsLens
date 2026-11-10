
"""Two-case structured Gemini development smoke test.

Offline by default. Explicit --live required.
No retries, SQL execution, production integration, or fallback.
"""

import argparse
import hashlib
import json
import os
from pathlib import Path

from agent.structured_gemini_proposer import (
    StructuredGeminiProposer,
)
from agent.structured_semantic_intent import (
    compare_intents,
    validate_intent,
)

ROOT = Path(__file__).resolve().parents[1]
REFERENCE = ROOT / "reports/stage5_15f_frozen_reference.json"
OUTPUT = ROOT / "reports/stage5_15g3_structured_live.json"

EXPECTED_SHA256 = (
    "e66991b1f39a6ac45c16c8881e8be707"
    "e096c91750cba22c2151c78e0f768d76"
)


def load_questions():
    data = json.loads(
        REFERENCE.read_text(encoding="utf-8-sig")
    )

    canonical = json.dumps(
        data,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )

    digest = hashlib.sha256(
        canonical.encode("utf-8")
    ).hexdigest()

    if digest != EXPECTED_SHA256:
        raise ValueError("Frozen reference fingerprint mismatch")

    cases = {
        case["id"]: case
        for case in data["scored_cases"]
    }

    return {
        case_id: cases[case_id]["question"]
        for case_id in ("F06", "F08")
    }


def reference_intents():
    common = {
        "contract": "opslens.structured-intent.v1",
        "execution_authorized": False,
        "completion_eligible": False,
        "evidence_state": "NOT_ASSESSED",
    }

    f06 = {
        **common,
        "handling": "UNSUPPORTED_SCOPE",
        "metric": "refund_rate",
        "period": "2018-06",
        "operations": [
            {
                "kind": "FILTER",
                "field": "order_value_myr",
                "operator": "gt",
                "value": 200,
            },
            {
                "kind": "FILTER",
                "field": "payment_method",
                "operator": "eq",
                "value": "credit_card",
            },
        ],
        "clarifications": [],
    }

    f08 = {
        **common,
        "handling": "CLARIFICATION_REQUIRED",
        "metric": "refund_rate",
        "period": None,
        "operations": [],
        "clarifications": [
            "Which holiday period and year do you mean?"
        ],
    }

    validate_intent(f06)
    validate_intent(f08)

    return {"F06": f06, "F08": f08}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--live", action="store_true")
    parser.add_argument("--model", default=None)
    args = parser.parse_args()

    questions = load_questions()
    references = reference_intents()

    if not args.live:
        print("=== STAGE 5.15G.3 OFFLINE PREFLIGHT ===")
        print("Frozen source: VERIFIED")
        print("Structured references: VALID")
        print("Cases: F06, F08")
        print("Gemini requests: 0")
        print("Use --live for the two-case smoke test.")
        return

    if OUTPUT.exists():
        raise SystemExit(
            "Existing report found. No overwrite or requests."
        )

    from dotenv import load_dotenv
    from google import genai

    load_dotenv(ROOT / ".env", override=False)

    key = (
        os.getenv("GEMINI_API_KEY")
        or os.getenv("GOOGLE_API_KEY")
    )
    model = (
        args.model
        or os.getenv("OPSLENS_SEMANTIC_MODEL")
    )

    if not key:
        raise SystemExit("Gemini credentials unavailable")

    if not model:
        raise SystemExit("Gemini model not configured")

    client = genai.Client(api_key=key)
    proposer = StructuredGeminiProposer(client, model)
    records = []

    print("=== STAGE 5.15G.3 LIVE SMOKE TEST ===")

    try:
        for case_id in ("F06", "F08"):
            record = {
                "id": case_id,
                "outcome": "FAILED",
                "error_type": None,
                "candidate": None,
                "comparison": None,
                "full_structural_match": False,
            }

            try:
                candidate = proposer.propose(
                    questions[case_id]
                )

                comparison = compare_intents(
                    candidate,
                    references[case_id],
                )

                matched = all([
                    comparison["handling_match"],
                    comparison["metric_match"],
                    comparison["period_match"],
                    comparison["operations_match"],
                    comparison["clarification_required_match"],
                ])

                record.update({
                    "outcome": "ACCEPTED",
                    "candidate": candidate,
                    "comparison": comparison,
                    "full_structural_match": bool(matched),
                })

                print(case_id, "ACCEPTED")
                print(
                    "  handling:",
                    candidate["handling"],
                    "| match:",
                    comparison["handling_match"],
                )
                print(
                    "  metric:",
                    candidate["metric"],
                    "| match:",
                    comparison["metric_match"],
                )
                print(
                    "  period:",
                    candidate["period"],
                    "| match:",
                    comparison["period_match"],
                )
                print(
                    "  operations match:",
                    comparison["operations_match"],
                )

                for operation in candidate["operations"]:
                    print("  operation:", operation)

                print(
                    "  clarification needed:",
                    bool(candidate["clarifications"]),
                    "| match:",
                    comparison["clarification_required_match"],
                )
                print(
                    "  full structural match:",
                    matched,
                )

            except Exception as exc:
                cause = exc.__cause__
                record["error_type"] = (
                    type(cause).__name__
                    if cause is not None
                    else type(exc).__name__
                )

                print(
                    case_id,
                    "FAILED",
                    record["error_type"],
                )

            records.append(record)

    finally:
        close = getattr(client, "close", None)
        if callable(close):
            close()

    accepted = sum(
        r["outcome"] == "ACCEPTED"
        for r in records
    )

    matches = sum(
        r["full_structural_match"]
        for r in records
    )

    report = {
        "contract": "opslens.stage5_15g3.structured-smoke.v1",
        "model": model,
        "source_reference_sha256": EXPECTED_SHA256,
        "attempted": 2,
        "accepted": accepted,
        "full_structural_matches": matches,
        "records": records,
        "limitations": [
            "Development smoke test, not blind evaluation.",
            "Prompt includes examples related to F06 and F08.",
            "Clarification wording and completeness not scored.",
            "No independent adapter or schema capability verification.",
            "No retries or production execution.",
        ],
    }

    OUTPUT.write_text(
        json.dumps(
            report,
            indent=2,
            ensure_ascii=False,
        ) + "\n",
        encoding="utf-8",
    )

    print("\n=== STAGE 5.15G.3 SUMMARY ===")
    print("Attempted:", 2)
    print("Accepted:", accepted)
    print("Full structural matches:", matches)
    print("Report:", OUTPUT)
    print("Production modules unchanged.")


if __name__ == "__main__":
    main()
