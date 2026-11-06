
from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd


def pct(x):
    if pd.isna(x):
        return "n/a"
    return f"{x*100:.2f}%"


def money(x):
    if pd.isna(x):
        return "n/a"
    return f"{x:,.2f}"


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--project-root", default=".")
    args = parser.parse_args()

    root = Path(args.project_root).resolve()

    pnl_path = root / "data" / "processed" / "daily_pnl.csv"
    profit_path = root / "data" / "processed" / "order_profitability.csv"
    costs_path = root / "data" / "synthetic" / "product_cost_history.csv"
    campaigns_path = root / "data" / "synthetic" / "marketing_campaigns.csv"
    spend_path = root / "data" / "synthetic" / "marketing_spend_daily.csv"
    returns_path = root / "data" / "synthetic" / "returns.csv"
    inventory_path = root / "data" / "synthetic" / "inventory_weekly.csv"
    truth_path = root / "data" / "eval_ground_truth" / "incident_001.json"

    required = [
        pnl_path, profit_path, costs_path, campaigns_path,
        spend_path, returns_path, inventory_path, truth_path
    ]
    missing = [str(p) for p in required if not p.exists()]
    if missing:
        raise FileNotFoundError("Missing generated files:\n- " + "\n- ".join(missing))

    daily = pd.read_csv(pnl_path, parse_dates=["date"])
    profit = pd.read_csv(profit_path, parse_dates=["order_purchase_timestamp"])
    costs = pd.read_csv(costs_path, parse_dates=["effective_month"])
    campaigns = pd.read_csv(campaigns_path, parse_dates=["start_date", "end_date"])
    spend = pd.read_csv(spend_path, parse_dates=["date"])
    returns = pd.read_csv(returns_path, parse_dates=["return_date"])
    inventory = pd.read_csv(inventory_path, parse_dates=["week"])
    truth = json.loads(truth_path.read_text(encoding="utf-8"))

    incident_month = pd.Timestamp(truth["incident_month"])
    prev_month = incident_month - pd.offsets.MonthBegin(1)
    next_month = incident_month + pd.offsets.MonthBegin(1)

    profit["month"] = profit["order_purchase_timestamp"].dt.to_period("M").dt.to_timestamp()
    monthly = (
        profit.groupby("month", as_index=False)
        .agg(
            revenue=("revenue", "sum"),
            cogs=("cogs", "sum"),
            refunds=("refund_amount", "sum"),
            fulfillment_cost=("fulfillment_cost", "sum"),
            payment_processing_cost=("payment_processing_cost", "sum"),
            marketing_cost=("marketing_cost", "sum"),
            gross_profit=("gross_profit", "sum"),
            contribution_profit=("contribution_profit", "sum"),
            orders=("order_id", "nunique"),
        )
        .sort_values("month")
    )
    monthly["gross_margin_pct"] = monthly["gross_profit"] / monthly["revenue"].replace(0, np.nan)
    monthly["contribution_margin_pct"] = monthly["contribution_profit"] / monthly["revenue"].replace(0, np.nan)

    focus = monthly[monthly["month"].isin([prev_month, incident_month, next_month])].copy()

    cur = monthly.loc[monthly["month"] == incident_month]
    prev = monthly.loc[monthly["month"] == prev_month]

    if cur.empty or prev.empty:
        raise RuntimeError("Could not find incident and previous month in profitability data.")

    cur = cur.iloc[0]
    prev = prev.iloc[0]

    metrics = {
        "revenue_growth": cur["revenue"] / prev["revenue"] - 1 if prev["revenue"] else np.nan,
        "profit_growth": cur["contribution_profit"] / prev["contribution_profit"] - 1 if prev["contribution_profit"] else np.nan,
        "gm_change_pp": (cur["gross_margin_pct"] - prev["gross_margin_pct"]) * 100,
        "cm_change_pp": (cur["contribution_margin_pct"] - prev["contribution_margin_pct"]) * 100,
        "cogs_growth": cur["cogs"] / prev["cogs"] - 1 if prev["cogs"] else np.nan,
        "marketing_growth": cur["marketing_cost"] / prev["marketing_cost"] - 1 if prev["marketing_cost"] else np.nan,
    }

    # Plausibility checks
    checks = []

    def add_check(name, passed, value, note):
        checks.append({
            "check": name,
            "passed": bool(passed),
            "value": value,
            "note": note,
        })

    add_check(
        "No negative revenue",
        (profit["revenue"] < 0).sum() == 0,
        int((profit["revenue"] < 0).sum()),
        "Observed Olist item prices should not become negative."
    )
    add_check(
        "COGS populated",
        profit["cogs"].isna().mean() < 0.001,
        float(profit["cogs"].isna().mean()),
        "Synthetic cost join should cover essentially all order lines."
    )
    add_check(
        "Reasonable gross margins",
        ((profit["gross_margin_pct"] >= -0.5) & (profit["gross_margin_pct"] <= 0.8)).mean() > 0.98,
        float(((profit["gross_margin_pct"] >= -0.5) & (profit["gross_margin_pct"] <= 0.8)).mean()),
        "Most order-level gross margins should fall inside a broad plausible range."
    )
    add_check(
        "Reasonable contribution margins",
        ((profit["contribution_margin_pct"] >= -1.5) & (profit["contribution_margin_pct"] <= 0.8)).mean() > 0.97,
        float(((profit["contribution_margin_pct"] >= -1.5) & (profit["contribution_margin_pct"] <= 0.8)).mean()),
        "Contribution margin may be negative for acquired/returned orders but should not be wildly implausible for most orders."
    )
    add_check(
        "Returns are sparse",
        len(returns) / profit["order_id"].nunique() < 0.20,
        len(returns) / profit["order_id"].nunique(),
        "Synthetic returns should remain a minority of delivered orders."
    )
    add_check(
        "Campaign attribution is sparse",
        profit["campaign_id"].notna().mean() < 0.40,
        float(profit["campaign_id"].notna().mean()),
        "Most orders should not be force-attributed to campaigns."
    )
    add_check(
        "Marketing spend non-negative",
        (spend["spend"] >= 0).all(),
        float(spend["spend"].min()),
        "Daily campaign spend must never be negative."
    )
    add_check(
        "Inventory non-negative",
        (inventory["estimated_on_hand_end"] >= 0).all(),
        int(inventory["estimated_on_hand_end"].min()),
        "Inventory cannot be negative in this simplified model."
    )

    # Incident checks
    affected = truth.get("affected_categories", [])
    incident_cost = costs[
        (costs["effective_month"] == incident_month)
        & (costs["category"].isin(affected))
    ]
    previous_cost = costs[
        (costs["effective_month"] == prev_month)
        & (costs["category"].isin(affected))
    ]
    merged_cost = incident_cost[["product_id", "unit_cost"]].merge(
        previous_cost[["product_id", "unit_cost"]],
        on="product_id",
        suffixes=("_incident", "_prev"),
    )
    merged_cost["growth"] = merged_cost["unit_cost_incident"] / merged_cost["unit_cost_prev"] - 1

    supplier_cost_growth = merged_cost["growth"].median() if len(merged_cost) else np.nan

    inc_campaign = campaigns[campaigns["campaign_id"] == "CMP_GROWTH_01"]
    inc_campaign_spend = spend.loc[
        spend["campaign_id"] == "CMP_GROWTH_01", "spend"
    ].sum()

    add_check(
        "Supplier shock visible",
        pd.notna(supplier_cost_growth) and supplier_cost_growth > 0.05,
        float(supplier_cost_growth) if pd.notna(supplier_cost_growth) else np.nan,
        "Affected categories should show a clearly observable cost increase."
    )
    add_check(
        "GrowthMax exists",
        len(inc_campaign) == 1,
        int(len(inc_campaign)),
        "The controlled campaign must exist exactly once."
    )
    add_check(
        "GrowthMax has material spend",
        inc_campaign_spend > 50000,
        float(inc_campaign_spend),
        "The campaign should be large enough to matter to profitability."
    )

    # This is diagnostic, not a hard pass: the real Olist revenue pattern may not create a literal profit decline.
    incident_pattern = {
        "revenue_growth_mom": float(metrics["revenue_growth"]),
        "contribution_profit_growth_mom": float(metrics["profit_growth"]),
        "gross_margin_change_pp": float(metrics["gm_change_pp"]),
        "contribution_margin_change_pp": float(metrics["cm_change_pp"]),
        "cogs_growth_mom": float(metrics["cogs_growth"]),
        "marketing_cost_growth_mom": float(metrics["marketing_growth"]) if pd.notna(metrics["marketing_growth"]) else None,
    }

    print("\n" + "=" * 78)
    print("OPSLENS PHASE 1 BUSINESS-REALISM AUDIT")
    print("=" * 78)
    print(f"Incident month: {incident_month.date()}")
    print(f"Affected categories: {', '.join(affected)}")

    print("\nMONTHLY ECONOMICS")
    print(f"{'Metric':32} {'Previous':>14} {'Incident':>14}")
    print("-" * 64)
    for key, label in [
        ("revenue", "Revenue"),
        ("cogs", "COGS"),
        ("marketing_cost", "Marketing cost"),
        ("refunds", "Refunds"),
        ("gross_profit", "Gross profit"),
        ("contribution_profit", "Contribution profit"),
        ("gross_margin_pct", "Gross margin"),
        ("contribution_margin_pct", "Contribution margin"),
        ("orders", "Orders"),
    ]:
        pv = prev[key]
        cv = cur[key]
        if "margin" in key:
            ptxt, ctxt = pct(pv), pct(cv)
        elif key == "orders":
            ptxt, ctxt = f"{int(pv):,}", f"{int(cv):,}"
        else:
            ptxt, ctxt = money(pv), money(cv)
        print(f"{label:32} {ptxt:>14} {ctxt:>14}")

    print("\nMONTH-ON-MONTH SIGNAL")
    print(f"Revenue growth:                 {pct(metrics['revenue_growth'])}")
    print(f"Contribution profit growth:     {pct(metrics['profit_growth'])}")
    print(f"Gross margin change:            {metrics['gm_change_pp']:+.2f} pp")
    print(f"Contribution margin change:     {metrics['cm_change_pp']:+.2f} pp")
    print(f"COGS growth:                    {pct(metrics['cogs_growth'])}")
    print(f"Marketing cost growth:          {pct(metrics['marketing_growth'])}")
    print(f"Median affected-product cost Δ: {pct(supplier_cost_growth)}")
    print(f"GrowthMax total spend:          {money(inc_campaign_spend)}")

    print("\nPLAUSIBILITY / INTEGRITY CHECKS")
    passed = 0
    for c in checks:
        status = "PASS" if c["passed"] else "FAIL"
        passed += int(c["passed"])
        print(f"[{status}] {c['check']}: {c['value']}")
        print(f"       {c['note']}")

    print("\nSCENARIO VERDICT")
    revenue_up = metrics["revenue_growth"] > 0
    profit_down = metrics["profit_growth"] < 0
    margin_down = metrics["cm_change_pp"] < 0

    if revenue_up and profit_down and margin_down:
        verdict = "STRONG"
        explanation = (
            "The controlled incident already exhibits the flagship pattern: "
            "revenue increased while contribution profit and margin deteriorated."
        )
    elif revenue_up and margin_down:
        verdict = "USABLE_BUT_NEEDS_CALIBRATION"
        explanation = (
            "Revenue increased and margin deteriorated, but absolute contribution profit "
            "did not fall. The scenario is economically plausible but should be calibrated "
            "before using 'revenue up, profit down' as ground truth."
        )
    else:
        verdict = "RECALIBRATE"
        explanation = (
            "The selected real month does not yet produce the intended observable anomaly. "
            "Do not proceed to agent evaluation until the incident generator is calibrated."
        )

    print(f"{verdict}: {explanation}")
    print(f"\nChecks passed: {passed}/{len(checks)}")

    report = {
        "incident_month": str(incident_month.date()),
        "affected_categories": affected,
        "incident_pattern": incident_pattern,
        "supplier_cost_growth_median": float(supplier_cost_growth) if pd.notna(supplier_cost_growth) else None,
        "growthmax_total_spend": float(inc_campaign_spend),
        "checks": checks,
        "verdict": verdict,
        "verdict_explanation": explanation,
    }

    out_path = root / "docs" / "phase1_business_realism_audit.json"
    out_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(f"\nSaved audit report: {out_path}")


if __name__ == "__main__":
    main()
