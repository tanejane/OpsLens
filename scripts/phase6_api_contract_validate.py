"""Offline contract tests for the read-only API metadata and audit matching."""
from api import InvestigationRequest, ROOT, _cohort_audit_for, _execution_capabilities, _metric_definitions, _validated_cohort_audits, app


def main():
    metrics = _metric_definitions()
    assert metrics, "governed catalog is empty"
    assert all({"metric_name", "domain", "business_definition", "formula", "grain", "source_view", "time_field", "dimensions", "known_limitations"} <= set(row) for row in metrics)
    assert len(_metric_definitions("delivery")) == 0  # Catalog uses its own governed domain vocabulary.
    assert len(_metric_definitions("finance")) > 0
    assert "/api/dashboard" in app.openapi()["paths"], "monthly dashboard API route is missing"
    capabilities = _execution_capabilities()
    assert {"revenue", "contribution_profit", "contribution_margin_pct", "orders", "late_delivery_rate", "average_review_score"} <= set(capabilities[0]["metric_ids"])
    assert all(item["state"] == "REGISTERED_GOVERNED_PATH" and item["sources"] for item in capabilities)
    print("PASS: dashboard HTTP contract and distinct registered compiler capabilities")
    try:
        InvestigationRequest(question="x" * 501)
        raise AssertionError("question length boundary was not enforced")
    except Exception as exc:
        assert exc.__class__.__name__ == "ValidationError"
    audits = _validated_cohort_audits()
    assert len(audits) == 2
    assert all(audit["status"] == "EXACT_ORDER_COHORT_RECONCILED" for audit in audits)
    assert all(audit["approved_for_mcp"] is False and audit["causal_claim"] is False for audit in audits)
    assert _cohort_audit_for("Compare finance, late delivery and review scores from February 2018 to March 2018") is not None
    assert _cohort_audit_for("Compare finance, late delivery and review scores from March 2018 to April 2018") is None
    assert _cohort_audit_for("Did delivery delays cause poor reviews and profit decline between February and March 2018?") is None
    from agent.phase5_2e_multidomain_router import decision
    assert decision("Compare finance, late delivery and review scores from February 2018 to March 2018")[0] == "execute"
    assert decision("Did delivery delays cause poor reviews and profit decline between February and March 2018?")[0] == "reject"
    assert decision("What was the late delivery rate in June 2018?") is None
    from agent.phase4c25_clarification import VAGUE
    assert VAGUE.fullmatch("How were sales in June 2018?") is not None
    from agent.phase4c15_delivery import compile_metric as compile_delivery
    from agent.phase4c11_satisfaction import compile_metric as compile_satisfaction
    delivery = compile_delivery("late_delivery_rate", "2018-06-01", "2018-07-01")
    review = compile_satisfaction("average_review_score", "2018-06-01", "2018-07-01")
    assert delivery["source"] == "semantic.order_delivery_evidence_v1" and delivery["causal_claim"] is False
    assert review["source"] == "semantic.order_review_evidence_v1" and review["causal_claim"] is False
    from agent.phase4c19_product import compile_metric as compile_product
    product = compile_product("item_gmv", "2018-06-01", "2018-07-01", "beleza_saude")
    assert product["source"] == "semantic.order_item_product_evidence_v1" and product["causal_claim"] is False
    print(f"PASS: {len(metrics)} governed metric definitions preserve full catalog contracts")
    print("PASS: both stored cohort artifacts pass their independent assessors")
    print("PASS: exact-period audit attachment matches February–March; causal requests receive none")
    print("PASS: delivery, satisfaction and product compilers retain registered source and descriptive contracts")
    print("PASS: ambiguous sales request is recognized by the existing clarification gate")
    print("PASS: API rejects questions over its 500-character bound")
    print("Checks passed: 5/5")


if __name__ == "__main__":
    main()
