"""Deterministic tests for Gemini's bounded post-evidence explanation selector."""
from __future__ import annotations

import json
from pathlib import Path

from agent.phase5_1_explanation import _codes_for, select_explanation, validate_plan


def run_immediate(coroutine):
    """Drive this pure async stub path without depending on a host event loop."""
    try:
        coroutine.send(None)
    except StopIteration as completed:
        return completed.value
    raise AssertionError("the deterministic model stub unexpectedly yielded asynchronous I/O")


def main():
    fixtures = json.loads((Path(__file__).resolve().parents[1] / "frontend/tests/fixtures/backend-results.json").read_text(encoding="utf-8"))
    finance = fixtures["finance_investigation"]
    candidates = _codes_for("Why did revenue grow but contribution profit fall?", finance)
    assert "finance_divergence" in candidates
    assert "cost_per_order_context" in candidates
    good = {"explanation_type": "cost_per_order_context", "evidence_refs": candidates["cost_per_order_context"]}
    assert validate_plan(good, candidates)["status"] == "VALIDATED"
    assert validate_plan({**good, "statement": "Marketing caused the decline"}, candidates) is None
    assert validate_plan({**good, "evidence_refs": ["made_up.number"]}, candidates) is None
    assert validate_plan({"explanation_type": "finance_divergence", "evidence_refs": candidates["cost_per_order_context"]}, candidates) is None

    gap = fixtures["unsupported_evidence_gap"]
    assert _codes_for("Why?", gap) == {}
    unsupported = fixtures["product_unsupported_saved"]
    assert _codes_for("What was category GMV?", unsupported) == {}

    async def call(prompt, envelope):
        context = json.loads(envelope)
        assert "available_explanations" in context
        return json.dumps(good)

    accepted = run_immediate(select_explanation("Investigate cost changes", finance, call))
    assert accepted and accepted["explanation_type"] == "cost_per_order_context"
    print("PASS: explanation selection is evidence-bound, structured, and non-authorizing")


if __name__ == "__main__":
    main()
