
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

    # Isolation check across INC001-008
    month_map = json.loads(
        (root / "data" / "eval_ground_truth" / "all_incident_months_v1.json")
        .read_text(encoding="utf-8")
    )
    months = list(month_map.values())
    add("INC_001–INC_008 months are isolated", len(months) == len(set(months)), month_map)

    # INC005
    t5 = json.loads(
        (root / "data" / "eval_ground_truth" / "incident_005.json")
        .read_text(encoding="utf-8")
    )
    mix = pd.read_csv(root / "data" / "synthetic" / "product_mix_overrides.csv")
    add("INC_005 mix override table non-empty", len(mix) > 100, len(mix))
    add(
        "INC_005 has both promoted and deemphasized categories",
        {"mix_shift_toward_lower_margin", "mix_shift_away_from_higher_margin"}.issubset(
            set(mix["mix_override_reason"].unique())
        ),
        sorted(mix["mix_override_reason"].unique().tolist()),
    )
    add(
        "INC_005 targets 3 low-margin categories",
        len(t5["low_margin_categories_promoted"]) == 3,
        len(t5["low_margin_categories_promoted"]),
    )

    # INC006
    t6 = json.loads(
        (root / "data" / "eval_ground_truth" / "incident_006.json")
        .read_text(encoding="utf-8")
    )
    econ = pd.read_csv(
        root / "data" / "synthetic" / "inc006_order_marketing_economics.csv"
    )
    add("INC_006 enough attributed orders", len(econ) >= 100, len(econ))
    add(
        "INC_006 marketing costs positive",
        (econ["allocated_marketing_cost"] > 0).all(),
        float(econ["allocated_marketing_cost"].sum()),
    )
    add(
        "INC_006 incentive costs positive",
        (econ["campaign_incentive_cost"] > 0).all(),
        float(econ["campaign_incentive_cost"].sum()),
    )

    # INC007
    t7 = json.loads(
        (root / "data" / "eval_ground_truth" / "incident_007.json")
        .read_text(encoding="utf-8")
    )
    stock = pd.read_csv(root / "data" / "synthetic" / "stockout_events.csv")
    add("INC_007 exactly 3 stockout SKUs", stock["product_id"].nunique() == 3, stock["product_id"].nunique())
    add(
        "INC_007 stockout availability materially reduced",
        (stock["availability_multiplier"] <= 0.20).all(),
        float(stock["availability_multiplier"].max()),
    )

    # INC008
    t8 = json.loads(
        (root / "data" / "eval_ground_truth" / "incident_008.json")
        .read_text(encoding="utf-8")
    )
    cx = pd.read_csv(root / "data" / "synthetic" / "cx_incident_overrides.csv")
    add("INC_008 enough affected orders", len(cx) >= 20, len(cx))
    add(
        "INC_008 delivery delays positive",
        (cx["extra_delivery_delay_days"] > 0).all(),
        int(cx["extra_delivery_delay_days"].min()),
    )
    scored = cx.dropna(subset=["original_review_score"])
    add(
        "INC_008 effective review scores do not improve",
        (scored["effective_review_score"] <= scored["original_review_score"]).all(),
        len(scored),
    )
    add(
        "INC_008 exactly two affected sellers",
        len(t8["affected_sellers"]) == 2,
        len(t8["affected_sellers"]),
    )

    print("=" * 78)
    print("OPSLENS BATCH B — CAUSAL/REALISM AUDIT")
    print("=" * 78)

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

    (root / "docs" / "batch_b_audit.json").write_text(
        json.dumps(report, indent=2), encoding="utf-8"
    )


if __name__ == "__main__":
    main()
