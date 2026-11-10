"""Bounded, opt-in Gemini semantic evaluation.

Offline by default. No SQL, coordinator, or completion-gate access.
"""

import argparse
import hashlib
import json
import os
from pathlib import Path

from agent.semantic_gemini_proposer import (
    SemanticGeminiProposer,
    CandidateGenerationError,
)
from agent.semantic_proposal import compare_to_reference

ROOT = Path(__file__).resolve().parents[1]
BENCHMARK = ROOT / "reports/stage5_15a_semantic_benchmark.json"

EXPECTED_SHA256 = (
    "bcde896a4b6a8884f0f4238540aa6df"
    "886c6f20907e52e634064905208364b60"
)


def load_benchmark():
    data = json.loads(
        BENCHMARK.read_text(encoding="utf-8-sig")
    )

    canonical = json.dumps(
        data["cases"],
        sort_keys=True,
        ensure_ascii=False,
        separators=(",", ":"),
    )

    actual = hashlib.sha256(
        canonical.encode("utf-8")
    ).hexdigest()

    if actual != EXPECTED_SHA256:
        raise ValueError("Frozen benchmark fingerprint mismatch")

    if len(data["cases"]) != 14:
        raise ValueError("Expected 14 reference cases")

    return data["cases"]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--live", action="store_true")
    parser.add_argument("--model", default=None)
    parser.add_argument(
        "--max-cases", type=int, default=3
    )
    args = parser.parse_args()

    if not 1 <= args.max_cases <= 14:
        parser.error("--max-cases must be between 1 and 14")

    cases = load_benchmark()[:args.max_cases]

    if not args.live:
        print("=== STAGE 5.15E.3 DRY RUN ===")
        print("Frozen benchmark: VERIFIED")
        print("Selected case IDs:", [
            case["id"] for case in cases
        ])
        print("Model requests: 0")
        print("Use --live with --model for explicit execution.")
        return

    model = args.model or os.getenv(
        "OPSLENS_SEMANTIC_MODEL"
    )

    if not model or not model.strip():
        parser.error(
            "Specify --model or OPSLENS_SEMANTIC_MODEL"
        )

    # Credential loading is restricted to the explicit live path.
    try:
        from dotenv import load_dotenv
        load_dotenv(ROOT / ".env", override=False)
    except ImportError:
        pass

    key = (
        os.getenv("GEMINI_API_KEY")
        or os.getenv("GOOGLE_API_KEY")
    )

    if not key:
        raise SystemExit(
            "Gemini API key unavailable. Set GEMINI_API_KEY "
            "or GOOGLE_API_KEY locally. No requests made."
        )

    from google import genai

    output = (
        ROOT / "reports"
        / f"stage5_15e3_live_{args.max_cases}.json"
    )

    if output.exists():
        raise SystemExit(
            f"Report already exists: {output}. "
            "No requests made."
        )

    client = genai.Client(api_key=key)
    proposer = SemanticGeminiProposer(client, model)

    records = []

    try:
        for case in cases:
            record = {
                "id": case["id"],
                "reference_review_required": (
                    case["handling"] == "SCOPE_REVIEW_REQUIRED"
                ),
                "outcome": "FAILED",
                "error_type": None,
                "candidate": None,
                "comparison": None,
            }

            try:
                candidate = proposer.propose(case["question"])
                evaluation = compare_to_reference(
                    candidate, case
                )

                record["outcome"] = "ACCEPTED"
                record["candidate"] = candidate
                record["comparison"] = evaluation

                print(
                    case["id"],
                    "ACCEPTED",
                    "handling=" + str(
                        evaluation["handling_match"]
                    ),
                    "obligations=" + str(
                        evaluation["obligations_match"]
                    ),
                    "period=" + str(
                        evaluation["period_match"]
                    ),
                )

            except CandidateGenerationError as error:
                # Record error classes, not provider messages,
                # which may contain sensitive request details.
                cause = error.__cause__
                record["error_type"] = (
                    type(cause).__name__
                    if cause is not None
                    else type(error).__name__
                )
                print(
                    case["id"],
                    "FAILED",
                    record["error_type"],
                )

            except ValueError:
                record["error_type"] = "EvaluationValueError"
                print(case["id"], "EVALUATION FAILED")

            records.append(record)

    finally:
        close = getattr(client, "close", None)
        if callable(close):
            close()

    accepted = [
        record for record in records
        if record["outcome"] == "ACCEPTED"
    ]

    scored = [
        record for record in accepted
        if not record["reference_review_required"]
    ]

    handling_matches = sum(
        record["comparison"]["handling_match"]
        for record in scored
    )
    obligation_matches = sum(
        record["comparison"]["obligations_match"]
        for record in scored
    )
    complete_matches = sum(
        all(record["comparison"][field] for field in (
            "handling_match",
            "period_match",
            "obligations_match",
        ))
        for record in scored
    )

    false_supported = [
        record["id"]
        for record in scored
        if (
            record["candidate"]["handling"]
            == "SUPPORTED_CANDIDATE"
            and next(
                case["handling"]
                for case in cases
                if case["id"] == record["id"]
            ) != "SUPPORTED_CANDIDATE"
        )
    ]

    report = {
        "contract": "opslens.stage5_15e3.live-eval.v1",
        "benchmark_sha256": EXPECTED_SHA256,
        "model": model,
        "requested_cases": args.max_cases,
        "completed_requests": len(records),
        "accepted_candidates": len(accepted),
        "scored_candidates": len(scored),
        "handling_matches": handling_matches,
        "obligation_matches": obligation_matches,
        "complete_matches": complete_matches,
        "false_supported_cases": false_supported,
        "records": records,
        "limitations": [
            "Development benchmark; not independent holdout.",
            "Invalid responses excluded from match denominators.",
            "No retries or model fallback.",
            "Provider output is untrusted.",
            "No execution, evidence verification or completion.",
        ],
    }

    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(
            report, indent=2, ensure_ascii=False
        ) + "\n",
        encoding="utf-8",
    )

    print("\n=== STAGE 5.15E.3 SUMMARY ===")
    print(
        "Accepted:", len(accepted),
        "/", len(records),
    )
    print(
        "Handling agreement:",
        handling_matches, "/", len(scored),
    )
    print(
        "Obligation-set agreement:",
        obligation_matches, "/", len(scored),
    )
    print(
        "Complete agreement:",
        complete_matches, "/", len(scored),
    )
    print("False supported cases:", false_supported)
    print("Report:", output)
    print("Production code unchanged.")


if __name__ == "__main__":
    main()
