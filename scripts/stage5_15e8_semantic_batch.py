"""Bounded Gemini semantic benchmark with attempted-case scoring.

Explicit live opt-in. No retries, SQL, runtime integration, or
completion authorization. Raw accepted candidates are retained.
"""

import argparse
import hashlib
import json
import os
from pathlib import Path

from agent.semantic_gemini_proposer import (
    CandidateGenerationError,
    SemanticGeminiProposer,
)
from agent.semantic_alias_evaluation import evaluate_with_aliases

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "reports/stage5_15a_semantic_benchmark.json"

EXPECTED_DIGEST = (
    "bcde896a4b6a8884f0f4238540aa6df"
    "886c6f20907e52e634064905208364b60"
)

def benchmark():
    data = json.loads(SOURCE.read_text(encoding="utf-8-sig"))
    canonical = json.dumps(
        data["cases"],
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    digest = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
    if digest != EXPECTED_DIGEST:
        raise ValueError("Frozen benchmark digest mismatch")
    return {case["id"]: case for case in data["cases"]}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--live", action="store_true")
    parser.add_argument(
        "--ids", nargs="+", default=["S04", "S05", "S06", "S07"]
    )
    parser.add_argument("--model", default=None)
    args = parser.parse_args()

    cases = benchmark()
    ids = args.ids

    if not ids or len(ids) > 4:
        parser.error("Select between 1 and 4 cases")

    if len(ids) != len(set(ids)):
        parser.error("Duplicate case IDs")

    for case_id in ids:
        if case_id not in cases:
            parser.error(f"Unknown case ID: {case_id}")

    if not args.live:
        print("=== STAGE 5.15E.8 DRY RUN ===")
        print("Frozen benchmark: VERIFIED")
        print("Selected cases:", ids)
        print("Network requests: 0")
        print("Use --live to make bounded model requests.")
        return

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
        raise SystemExit("Model must be explicitly configured")

    filename = "stage5_15e8_" + "_".join(ids) + ".json"
    output = ROOT / "reports" / filename

    if output.exists():
        raise SystemExit("Report already exists; no requests made")

    client = genai.Client(api_key=key)
    proposer = SemanticGeminiProposer(client, model)

    records = []

    try:
        for case_id in ids:
            reference = cases[case_id]

            record = {
                "id": case_id,
                "outcome": "FAILED",
                "error_category": None,
                "candidate": None,
                "evaluation": None,
                "reference_review_required": (
                    reference["handling"] == "SCOPE_REVIEW_REQUIRED"
                ),
            }

            try:
                candidate = proposer.propose(reference["question"])
                evaluation = evaluate_with_aliases(
                    candidate, reference
                )

                record["outcome"] = "ACCEPTED"
                record["candidate"] = candidate
                record["evaluation"] = evaluation

                print(
                    case_id,
                    "ACCEPTED",
                    "handling=" + str(evaluation["handling_match"]),
                    "period=" + str(evaluation["period_match"]),
                    "exact=" + str(
                        evaluation["exact"]["obligations_match"]
                    ),
                    "reviewed=" + str(
                        evaluation["normalized_obligations_match"]
                    ),
                )

            except CandidateGenerationError as error:
                cause = error.__cause__
                record["error_category"] = (
                    type(cause).__name__
                    if cause is not None
                    else "CandidateGenerationError"
                )
                print(
                    case_id, "FAILED", record["error_category"]
                )

            except ValueError:
                record["error_category"] = "EvaluationValueError"
                print(case_id, "EVALUATION FAILED")

            records.append(record)

    finally:
        close = getattr(client, "close", None)
        if callable(close):
            close()

    scored = [
        r for r in records
        if not r["reference_review_required"]
    ]
    accepted = [
        r for r in scored if r["outcome"] == "ACCEPTED"
    ]

    def count_match(field):
        return sum(
            r["evaluation"][field] is True
            for r in accepted
        )

    exact = sum(
        r["evaluation"]["handling_match"]
        and r["evaluation"]["period_match"]
        and r["evaluation"]["exact"]["obligations_match"]
        for r in accepted
    )

    reviewed = sum(
        r["evaluation"]["handling_match"]
        and r["evaluation"]["period_match"]
        and r["evaluation"]["normalized_obligations_match"]
        for r in accepted
    )

    false_supported = [
        r["id"] for r in accepted
        if (
            r["candidate"]["handling"] == "SUPPORTED_CANDIDATE"
            and cases[r["id"]]["handling"] != "SUPPORTED_CANDIDATE"
        )
    ]

    summary = {
        "attempted": len(records),
        "scored_attempts": len(scored),
        "accepted": len(accepted),
        "handling_matches": count_match("handling_match"),
        "period_matches": count_match("period_match"),
        "exact_complete_matches": exact,
        "reviewed_complete_matches": reviewed,
        "false_supported_cases": false_supported,
    }

    report = {
        "contract": "opslens.stage5_15e8.live-batch.v1",
        "benchmark_sha256": EXPECTED_DIGEST,
        "model": model,
        "case_ids": ids,
        "summary": summary,
        "records": records,
        "limitations": [
            "Development benchmark, not independent holdout.",
            "Failures count as nonmatches among attempted scored cases.",
            "Reviewed aliases are evaluation-only.",
            "No retries or fallback.",
            "No SQL execution, verified evidence, or completion.",
        ],
    }

    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(report, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )

    print("\n=== STAGE 5.15E.8 SUMMARY ===")
    for name, value in summary.items():
        print(name + ":", value)

    print("Report:", output)
    print("Production modules unchanged.")


if __name__ == "__main__":
    main()
