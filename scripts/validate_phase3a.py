
from __future__ import annotations

import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]

if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


from agent.graph import (
    evidence_sufficiency,
    investigation_graph,
)
from agent.state import (
    EvidenceStrength,
    HypothesisStatus,
)


def main():
    print("=" * 86)
    print("OPSLENS PHASE 3A — INVESTIGATION STATE + CONTROL LOOP VALIDATION")
    print("=" * 86)

    checks = []

    def add(name, ok, value):
        checks.append((name, bool(ok), value))

    initial = {
        "question": "Revenue increased but profit fell. Investigate why.",
        "investigation_id": "phase3a-test",
        "primary_metric": None,
        "comparison_period": None,
        "business_context": {},
        "plan": [],
        "hypotheses": [],
        "evidence_ledger": [],
        "conflicts": [],
        "missing_evidence": [],
        "current_step": 0,
        "step_budget": 4,
        "tool_call_budget": 4,
        "tool_calls_used": 0,
        "stop_reason": None,
        "confidence": 0.0,
        "conclusion": None,
        "recommended_actions": [],
    }

    result = investigation_graph.invoke(initial)

    add(
        "Graph initializes flagship business question",
        result["primary_metric"] == "contribution_profit",
        result["primary_metric"],
    )

    add(
        "Investigation plan is explicit",
        len(result["plan"]) == 5,
        len(result["plan"]),
    )

    add(
        "Hypothesis lifecycle exists",
        len(result["hypotheses"]) == 4
        and any(
            h["status"] == HypothesisStatus.TESTING
            for h in result["hypotheses"]
        ),
        [h["status"] for h in result["hypotheses"]],
    )

    add(
        "Application-owned step budget stops loop",
        result["stop_reason"] == "TOOL_BUDGET_EXHAUSTED"
        or result["stop_reason"] == "STEP_BUDGET_EXHAUSTED",
        result["stop_reason"],
    )

    add(
        "No unsupported causal conclusion fabricated",
        "No hypothesis has sufficient support yet"
        in result["conclusion"],
        result["conclusion"],
    )

    # Direct sufficiency-rule test with controlled evidence.
    supported_state = dict(initial)
    supported_state["hypotheses"] = [
        {
            "hypothesis_id": "H1",
            "statement": "Supplier costs increased.",
            "status": HypothesisStatus.SUPPORTED,
            "rationale": "Controlled test.",
            "evidence_for": ["E1", "E2"],
            "evidence_against": [],
            "confidence": 0.88,
            "next_test": None,
        }
    ]
    supported_state["evidence_ledger"] = [
        {
            "evidence_id": "E1",
            "source_type": "sql",
            "source_ref": "semantic.order_economics",
            "claim": "COGS increased faster than revenue.",
            "value": {"cogs_growth": 18.5, "revenue_growth": 16.5},
            "supports_hypotheses": ["H1"],
            "contradicts_hypotheses": [],
            "strength": EvidenceStrength.STRONG,
            "limitations": [],
        },
        {
            "evidence_id": "E2",
            "source_type": "document",
            "source_ref": "supplier_note",
            "claim": "Supplier cost increase was documented.",
            "value": {"median_increase_pct": 8.66},
            "supports_hypotheses": ["H1"],
            "contradicts_hypotheses": [],
            "strength": EvidenceStrength.MODERATE,
            "limitations": [],
        },
    ]

    sufficiency = evidence_sufficiency(supported_state)

    add(
        "Evidence sufficiency can stop on supported hypothesis",
        sufficiency["stop_reason"] == "SUFFICIENT_EVIDENCE",
        sufficiency,
    )

    conflicting_state = dict(supported_state)
    conflicting_state["hypotheses"] = [
        {
            **supported_state["hypotheses"][0],
            "status": HypothesisStatus.CONFLICTING,
        }
    ]

    conflict_result = evidence_sufficiency(conflicting_state)

    add(
        "Conflicting evidence prevents premature conclusion",
        conflict_result["stop_reason"] is None
        and bool(conflict_result["missing_evidence"]),
        conflict_result,
    )

    passed = 0

    for name, ok, value in checks:
        print(
            f"[{'PASS' if ok else 'FAIL'}] "
            f"{name}: {value}"
        )
        passed += int(ok)

    print(f"\nChecks passed: {passed}/{len(checks)}")
    verdict = "PASS" if passed == len(checks) else "REVIEW"
    print("VERDICT:", verdict)

    if verdict != "PASS":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
