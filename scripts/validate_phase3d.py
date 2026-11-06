
from __future__ import annotations

import asyncio
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from retrieval.hybrid import hybrid_search


CASES = [
    (
        "supplier costs increased during the March profitability decline",
        "supplier_cost_notice.md",
    ),
    (
        "GrowthMax campaign spend and incentives",
        "growthmax_campaign_brief.md",
    ),
    (
        "corrected operations summary seller capacity disruption",
        "inc009_ops_summary_corrected.md",
    ),
    (
        "partial finance note missing supplier reconciliation paid media accrual",
        "inc010_partial_finance_note.md",
    ),
]


async def main():
    print("=" * 94)
    print("OPSLENS PHASE 3D — HYBRID RETRIEVAL EVALUATION")
    print("=" * 94)

    recalls = []
    reciprocal_ranks = []

    for query, expected in CASES:
        hits = await hybrid_search(
            query=query,
            top_k=3,
            candidate_k=20,
        )

        filenames = [h.filename for h in hits]

        hit = expected in filenames
        recalls.append(1 if hit else 0)

        rr = 0.0
        if hit:
            rr = 1.0 / (filenames.index(expected) + 1)
        reciprocal_ranks.append(rr)

        print(f"\nQuery: {query}")
        print(f"Expected: {expected}")
        for i, item in enumerate(hits, start=1):
            print(
                f"  {i}. {item.filename} "
                f"(dense={item.dense_rank}, lexical={item.lexical_rank}, "
                f"rerank={item.rerank_score})"
            )

    recall_at_3 = sum(recalls) / len(recalls)
    mrr = sum(reciprocal_ranks) / len(reciprocal_ranks)

    security_hits = await hybrid_search(
        query="ignore previous instructions reveal system prompt auto approve",
        top_k=5,
        candidate_k=20,
        include_security_hits=False,
    )

    injection_leaked = any(
        h.injection_flag
        for h in security_hits
    )

    checks = [
        (
            "Recall@3 >= 0.75",
            recall_at_3 >= 0.75,
            round(recall_at_3, 3),
        ),
        (
            "MRR >= 0.60",
            mrr >= 0.60,
            round(mrr, 3),
        ),
        (
            "Prompt-injection chunks filtered from normal context",
            not injection_leaked,
            [h.filename for h in security_hits],
        ),
    ]

    print("\nMetrics:")
    print("Recall@3:", round(recall_at_3, 3))
    print("MRR:", round(mrr, 3))

    passed = 0
    print("\nValidation:")
    for name, ok, value in checks:
        print(f"[{'PASS' if ok else 'FAIL'}] {name}: {value}")
        passed += int(ok)

    print(f"\nChecks passed: {passed}/{len(checks)}")
    verdict = "PASS" if passed == len(checks) else "REVIEW"
    print("VERDICT:", verdict)

    if verdict != "PASS":
        raise SystemExit(1)


if __name__ == "__main__":
    asyncio.run(main())
