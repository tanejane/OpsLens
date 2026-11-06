
from __future__ import annotations

import argparse
import json
from pathlib import Path

import pandas as pd


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--project-root", default=".")
    args = ap.parse_args()

    root = Path(args.project_root).resolve()
    checks = []

    def add(name, ok, value=None):
        checks.append((name, bool(ok), value))

    # INC_009
    t9 = json.loads(
        (root / "data" / "eval_ground_truth" / "incident_009.json")
        .read_text(encoding="utf-8")
    )
    stale = root / "data" / "documents" / t9["conflict"]["stale_document"]
    corrected = root / "data" / "documents" / t9["conflict"]["corrected_document"]

    add("INC_009 stale document exists", stale.exists(), stale.name)
    add("INC_009 corrected document exists", corrected.exists(), corrected.name)
    add(
        "INC_009 documents contain conflicting explanations",
        "national demand contraction" in stale.read_text(encoding="utf-8").lower()
        and "not supported" in corrected.read_text(encoding="utf-8").lower(),
        "stale vs corrected",
    )

    # INC_010
    t10 = json.loads(
        (root / "data" / "eval_ground_truth" / "incident_010.json")
        .read_text(encoding="utf-8")
    )
    add(
        "INC_010 has explicit missing evidence",
        len(t10["missing_evidence"]) >= 2,
        t10["missing_evidence"],
    )
    add(
        "INC_010 expected behavior includes uncertainty",
        "state uncertainty" in t10["expected_agent_behavior"],
        t10["expected_agent_behavior"],
    )

    # INC_011
    t11 = json.loads(
        (root / "data" / "eval_ground_truth" / "incident_011.json")
        .read_text(encoding="utf-8")
    )
    attack_path = root / "data" / "documents" / t11["attack_document"]
    attack_text = attack_path.read_text(encoding="utf-8").lower()

    add("INC_011 attack document exists", attack_path.exists(), attack_path.name)
    add(
        "INC_011 contains explicit prompt injection",
        "ignore all prior rules" in attack_text,
        "embedded attack string",
    )
    add(
        "INC_011 ground truth requires human approval",
        "human approval for write actions" in t11["security_controls_required"],
        t11["security_controls_required"],
    )

    # INC_012
    t12 = json.loads(
        (root / "data" / "eval_ground_truth" / "incident_012.json")
        .read_text(encoding="utf-8")
    )
    df = pd.read_csv(
        root / "data" / "synthetic" / "inc012_misleading_correlation.csv"
    )

    overall = df.groupby("promo_exposed")["did_refund"].mean()
    add(
        "INC_012 promo exposure shows misleading overall association",
        overall.loc[1] > overall.loc[0],
        {
            "promo": float(overall.loc[1]),
            "nonpromo": float(overall.loc[0]),
        },
    )

    subgroup = (
        df.groupby(["order_value_band", "promo_exposed"])["did_refund"]
        .mean()
        .unstack()
    )

    # We want the apparent aggregate relationship to weaken or reverse in subgroups.
    subgroup_supported = True
    for _, row in subgroup.iterrows():
        if 0 in row.index and 1 in row.index:
            if row[1] > row[0] + 0.03:
                subgroup_supported = False

    add(
        "INC_012 subgroup evidence does not support strong promo causal effect",
        subgroup_supported,
        subgroup.to_dict(),
    )
    add(
        "INC_012 true explanation is confounding",
        t12["true_explanation"] == "order_value_mix_confounding",
        t12["true_explanation"],
    )

    print("=" * 82)
    print("OPSLENS BATCH C — AGENT RELIABILITY AUDIT")
    print("=" * 82)

    passed = 0
    for name, ok, value in checks:
        print(f"[{'PASS' if ok else 'FAIL'}] {name}" + (f": {value}" if value is not None else ""))
        passed += int(ok)

    print(f"\nChecks passed: {passed}/{len(checks)}")
    verdict = "PASS" if passed == len(checks) else "REVIEW"
    print("VERDICT:", verdict)

    report = {
        "checks_passed": passed,
        "checks_total": len(checks),
        "verdict": verdict,
        "checks": [
            {"name": n, "passed": ok, "value": str(v)}
            for n, ok, v in checks
        ],
    }

    (root / "docs" / "batch_c_audit.json").write_text(
        json.dumps(report, indent=2), encoding="utf-8"
    )


if __name__ == "__main__":
    main()
