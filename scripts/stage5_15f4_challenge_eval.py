"""Frozen-reference challenge evaluation.

Max 3 cases per invocation. Explicit live opt-in.
No model retries, SQL execution or production integration.
"""

import argparse
import hashlib
import json
import os
from pathlib import Path

from agent.semantic_gemini_proposer import SemanticGeminiProposer
from agent.semantic_alias_evaluation import evaluate_with_aliases

ROOT = Path(__file__).resolve().parents[1]
REFERENCE = ROOT / "reports/stage5_15f_frozen_reference.json"

EXPECTED_HASH = (
    "e66991b1f39a6ac45c16c8881e8be707"
    "e096c91750cba22c2151c78e0f768d76"
)

def read_reference():
    data = json.loads(
        REFERENCE.read_text(encoding="utf-8-sig")
    )

    canonical = json.dumps(
        data,
        sort_keys=True,
        ensure_ascii=False,
        separators=(",", ":"),
    )

    actual = hashlib.sha256(
        canonical.encode("utf-8")
    ).hexdigest()

    if actual != EXPECTED_HASH:
        raise ValueError("Frozen reference fingerprint changed")

    if data["status"] != "FROZEN_ASSISTANT_ANNOTATED":
        raise ValueError("Unexpected reference status")

    scored = {
        item["id"]: item
        for item in data["scored_cases"]
    }

    held = {
        item["id"]
        for item in data["held_cases"]
    }

    if len(scored) != 9 or held != {"F07"}:
        raise ValueError("Unexpected scoring population")

    if len(scored) != len(data["scored_cases"]):
        raise ValueError("Duplicate scored case IDs")

    return scored


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--live", action="store_true")
    parser.add_argument(
        "--ids",
        nargs="+",
        default=["F01", "F02", "F03"],
    )
    parser.add_argument("--model", default=None)
    args = parser.parse_args()

    scored = read_reference()
    ids = args.ids

    if not 1 <= len(ids) <= 3:
        parser.error("Choose between 1 and 3 cases")

    if len(set(ids)) != len(ids):
        parser.error("Duplicate case IDs")

    if any(case_id not in scored for case_id in ids):
        parser.error("Only the nine frozen scored cases are allowed")

    output = (
        ROOT / "reports"
        / ("stage5_15f4_" + "_".join(ids) + ".json")
    )

    if output.exists():
        raise SystemExit(
            "Report already exists; refusing to overwrite"
        )

    if not args.live:
        print("=== STAGE 5.15F.4 OFFLINE PREFLIGHT ===")
        print("Frozen reference: VERIFIED")
        print("Selected:", ids)
        print("Held F07: EXCLUDED")
        print("Gemini requests: 0")
        print("Run with --live to evaluate.")
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
        raise SystemExit("Gemini API key unavailable")

    if not model:
        raise SystemExit("Gemini model not configured")

    records = []
    client = genai.Client(api_key=key)
    proposer = SemanticGeminiProposer(client, model)

    print("=== STAGE 5.15F.4 LIVE EVALUATION ===")

    try:
        for case_id in ids:
            reference = scored[case_id]

            record = {
                "id": case_id,
                "outcome": "FAILED",
                "error_type": None,
                "candidate": None,
                "evaluation": None,
            }

            try:
                candidate = proposer.propose(
                    reference["question"]
                )

                evaluation = evaluate_with_aliases(
                    candidate,
                    reference,
                )

                record["outcome"] = "ACCEPTED"
                record["candidate"] = candidate
                record["evaluation"] = evaluation

                exact = evaluation["exact"]
                full_exact = (
                    evaluation["handling_match"]
                    and evaluation["period_match"]
                    and exact["obligations_match"]
                )

                print(
                    case_id,
                    "ACCEPTED",
                    "handling=" + str(
                        evaluation["handling_match"]
                    ),
                    "period=" + str(
                        evaluation["period_match"]
                    ),
                    "obligations=" + str(
                        exact["obligations_match"]
                    ),
                    "full_exact=" + str(full_exact),
                )

                print(
                    "  missing:",
                    exact["missing_obligations"],
                )
                print(
                    "  extra:",
                    exact["extra_obligations"],
                )

            except Exception as exc:
                # Avoid printing provider error messages,
                # raw responses or credentials.
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

    accepted = [
        r for r in records
        if r["outcome"] == "ACCEPTED"
    ]

    def matched(record, reviewed=False):
        evaluation = record["evaluation"]
        obligation_match = (
            evaluation["normalized_obligations_match"]
            if reviewed
            else evaluation["exact"]["obligations_match"]
        )
        return bool(
            evaluation["handling_match"]
            and evaluation["period_match"]
            and obligation_match
        )

    summary = {
        "attempted": len(ids),
        "accepted": len(accepted),
        "handling_matches": sum(
            r["evaluation"]["handling_match"]
            for r in accepted
        ),
        "period_matches": sum(
            r["evaluation"]["period_match"]
            for r in accepted
        ),
        "exact_full_matches": sum(
            matched(r) for r in accepted
        ),
        "reviewed_full_matches": sum(
            matched(r, reviewed=True)
            for r in accepted
        ),
        "false_supported_cases": [
            r["id"]
            for r in accepted
            if (
                r["candidate"]["handling"]
                == "SUPPORTED_CANDIDATE"
                and scored[r["id"]]["handling"]
                != "SUPPORTED_CANDIDATE"
            )
        ],
    }

    report = {
        "contract": "opslens.stage5_15f4.challenge-eval.v1",
        "model": model,
        "frozen_reference_sha256": EXPECTED_HASH,
        "case_ids": ids,
        "summary": summary,
        "records": records,
        "limitations": [
            "Assistant-annotated challenge, not blind.",
            "Failures count as nonmatches.",
            "Aliases are evaluation-only.",
            "Parameter fidelity is not assessed.",
            "No retries, SQL execution or authorization.",
        ],
    }

    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(
            report,
            indent=2,
            ensure_ascii=False,
        ) + "\n",
        encoding="utf-8",
    )

    print("\n=== SUMMARY ===")
    for key, value in summary.items():
        print(key + ":", value)

    print("Report:", output)
    print("Production coordinator unchanged.")


if __name__ == "__main__":
    main()
