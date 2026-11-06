
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

    # INC002
    t2 = json.loads(
        (root / "data" / "eval_ground_truth" / "incident_002.json")
        .read_text(encoding="utf-8")
    )
    rco = pd.read_csv(
        root / "data" / "synthetic" / "regional_capacity_overrides.csv"
    )
    add("INC_002 override table non-empty", len(rco) > 0, len(rco))
    add(
        "INC_002 modeled revenue loss is material but plausible",
        0.08 <= t2["modeled_revenue_loss_pct"] <= 0.25,
        t2["modeled_revenue_loss_pct"],
    )
    add(
        "INC_002 contains both lost-order and delay mechanisms",
        set(rco["capacity_impact"]) == {"lost_order_capacity", "delayed_fulfillment"},
        sorted(rco["capacity_impact"].unique().tolist()),
    )

    # INC003
    t3 = json.loads(
        (root / "data" / "eval_ground_truth" / "incident_003.json")
        .read_text(encoding="utf-8")
    )
    returns = pd.read_csv(root / "data" / "synthetic" / "returns.csv")
    quality = pd.read_csv(
        root / "data" / "synthetic" / "product_quality_events.csv"
    )
    injected = returns[
        returns["source_type"] == "controlled_synthetic_defect_incident"
    ]
    add("INC_003 injected defect returns >= 3", len(injected) >= 3, len(injected))
    add("INC_003 exactly two affected SKUs", quality["product_id"].nunique() == 2, quality["product_id"].nunique())
    add("INC_003 one affected seller", quality["seller_id"].nunique() == 1, quality["seller_id"].nunique())

    # INC004
    t4 = json.loads(
        (root / "data" / "eval_ground_truth" / "incident_004.json")
        .read_text(encoding="utf-8")
    )
    ed = pd.read_csv(
        root / "data" / "synthetic" / "effective_delivery_dates.csv"
    )
    impacted = ed[ed["incident_id"] == "INC_004"]
    add("INC_004 delayed orders >= 10", len(impacted) >= 10, len(impacted))
    add("INC_004 all injected delays are positive", (impacted["extra_delay_days"] > 0).all(), impacted["extra_delay_days"].min())
    add("INC_004 seller cluster has exactly 3 sellers", len(t4["affected_sellers"]) == 3, len(t4["affected_sellers"]))

    print("=" * 76)
    print("OPSLENS BATCH A V2 — CAUSAL/REALISM AUDIT")
    print("=" * 76)

    passed = 0
    for name, ok, value in checks:
        print(f"[{'PASS' if ok else 'FAIL'}] {name}" + (f": {value}" if value is not None else ""))
        passed += int(ok)

    print(f"\nChecks passed: {passed}/{len(checks)}")
    print("VERDICT:", "PASS" if passed == len(checks) else "REVIEW")

    report = {
        "checks_passed": passed,
        "checks_total": len(checks),
        "verdict": "PASS" if passed == len(checks) else "REVIEW",
        "checks": [
            {"name": n, "passed": ok, "value": str(v)}
            for n, ok, v in checks
        ],
    }
    (root / "docs" / "batch_a_v2_audit.json").write_text(
        json.dumps(report, indent=2), encoding="utf-8"
    )


if __name__ == "__main__":
    main()
