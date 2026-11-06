import json

import pytest

import api
from agent.phase5_2f_cohort_evidence import apply_cohort_evidence, CohortEvidenceRejected


@pytest.mark.parametrize("unrelated", [None, "{", "[]"])
def test_independent_may_june_attachment(tmp_path, monkeypatch, unrelated):
    name = "phase5_2b_cohort_audit.json"
    (tmp_path / name).write_bytes((api.ROOT / name).read_bytes())
    if unrelated is not None:
        (tmp_path / "phase5_2d_cohort_audit.json").write_text(unrelated)
    monkeypatch.setattr(api, "ROOT", tmp_path)
    audit = api._cohort_audit_for("Compare finance, late delivery and review scores from May 2018 to June 2018")
    assert audit == json.loads((tmp_path / name).read_text(encoding="utf-8-sig"))
    pairs = audit["month_pairs"]
    report = dict(status="THREE_DOMAIN_DESCRIPTIVE_EVIDENCE", causal_claim=False, approved_for_mcp=False,
                  periods={}, cohort_orders={}, conclusions=[], tool_trace=[], limitations=[], next_validations=[])
    for key, month in zip(("before", "after"), pairs):
        report["periods"][key] = [month["month_start"], month["month_end"]]
        report["cohort_orders"][key] = month["source_unique_orders"]
    evidence = apply_cohort_evidence(report, audit)["operational_cohort_evidence"]
    assert evidence["audit_contract"] == audit["contract"]
    report["periods"]["after"][1] = "2018-06-15"
    with pytest.raises(CohortEvidenceRejected, match="PERIOD_MISMATCH"):
        apply_cohort_evidence(report, audit)
