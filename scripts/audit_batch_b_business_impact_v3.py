
from __future__ import annotations

import argparse
import json
from pathlib import Path


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--project-root", default=".")
    args = ap.parse_args()

    root = Path(args.project_root).resolve()
    report = json.loads(
        (root / "docs" / "batch_b_business_impact_v3.json")
        .read_text(encoding="utf-8")
    )

    checks = []

    def add(name, ok, value):
        checks.append((name, bool(ok), value))

    i5 = report["INC_005"]
    add(
        "INC_005 low-margin revenue share increases",
        i5["low_margin_share_change_pp"] > 0.25,
        f"{i5['low_margin_share_change_pp']:+.2f} pp",
    )
    add(
        "INC_005 weighted gross margin declines",
        i5["margin_change_pp"] < -0.05,
        f"{i5['margin_change_pp']:+.2f} pp",
    )
    add(
        "INC_005 margin effect remains plausible",
        i5["margin_change_pp"] > -5.0,
        f"{i5['margin_change_pp']:+.2f} pp",
    )

    i6 = report["INC_006"]
    add(
        "INC_006 campaign creates measurable revenue growth",
        0.01 <= i6["revenue_growth_pct"] <= 0.08,
        f"{i6['revenue_growth_pct']:+.2%}",
    )
    add(
        "INC_006 contribution margin deteriorates",
        i6["contribution_margin_change_pp"] <= -1.0,
        f"{i6['contribution_margin_change_pp']:+.2f} pp",
    )
    add(
        "INC_006 profit underperforms revenue",
        i6["contribution_profit_growth_pct"] < i6["revenue_growth_pct"],
        (
            f"profit={i6['contribution_profit_growth_pct']:+.2%}, "
            f"revenue={i6['revenue_growth_pct']:+.2%}"
        ),
    )
    add(
        "INC_006 campaign spend remains plausible",
        30000 <= i6["campaign_spend"] <= 100000,
        round(i6["campaign_spend"], 2),
    )

    i7 = report["INC_007"]
    add(
        "INC_007 stockout affects observed lines",
        i7["affected_lines"] >= 3,
        i7["affected_lines"],
    )
    add(
        "INC_007 modeled revenue loss is positive",
        i7["modeled_lost_revenue"] > 0,
        round(i7["modeled_lost_revenue"], 2),
    )
    add(
        "INC_007 category revenue loss is material but plausible",
        0.01 <= i7["modeled_category_revenue_loss_pct"] <= 0.30,
        f"{i7['modeled_category_revenue_loss_pct']:.2%}",
    )

    i8 = report["INC_008"]
    add(
        "INC_008 review score declines materially",
        i8["review_score_change"] <= -0.50,
        f"{i8['review_score_change']:+.2f}",
    )
    add(
        "INC_008 added delay is operationally material",
        3.0 <= i8["average_added_delay_days"] <= 7.0,
        f"{i8['average_added_delay_days']:.2f} days",
    )
    add(
        "INC_008 negative-review rate increases",
        i8["negative_review_rate_change_pp"] > 0,
        f"{i8['negative_review_rate_change_pp']:+.2f} pp",
    )

    print("=" * 82)
    print("OPSLENS BATCH B V3 — BUSINESS IMPACT AUDIT")
    print("=" * 82)

    passed = 0
    for name, ok, value in checks:
        print(f"[{'PASS' if ok else 'FAIL'}] {name}: {value}")
        passed += int(ok)

    print(f"\nChecks passed: {passed}/{len(checks)}")
    verdict = "PASS" if passed == len(checks) else "CALIBRATE"
    print("VERDICT:", verdict)

    output = {
        "checks_passed": passed,
        "checks_total": len(checks),
        "verdict": verdict,
        "checks": [
            {"name": n, "passed": ok, "value": str(v)}
            for n, ok, v in checks
        ],
    }
    (root / "docs" / "batch_b_business_impact_audit_v3.json").write_text(
        json.dumps(output, indent=2), encoding="utf-8"
    )


if __name__ == "__main__":
    main()
