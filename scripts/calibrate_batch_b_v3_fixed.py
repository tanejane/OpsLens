
from __future__ import annotations

import argparse
import json
from pathlib import Path

import pandas as pd


def month_floor(s):
    return pd.to_datetime(s, errors="coerce").dt.to_period("M").dt.to_timestamp()


def load_profitability(root: Path) -> pd.DataFrame:
    path = root / "data" / "processed" / "order_profitability.csv"
    df = pd.read_csv(path)
    df["order_purchase_timestamp"] = pd.to_datetime(
        df["order_purchase_timestamp"], errors="coerce"
    )
    df["month"] = month_floor(df["order_purchase_timestamp"])

    required = {"order_id", "revenue", "cogs", "gross_profit", "contribution_profit"}
    missing = required - set(df.columns)
    if missing:
        raise RuntimeError(f"order_profitability.csv missing required columns: {sorted(missing)}")
    return df


def load_raw(root: Path):
    raw = root / "data" / "raw" / "olist"
    orders = pd.read_csv(raw / "olist_orders_dataset.csv")
    items = pd.read_csv(raw / "olist_order_items_dataset.csv")
    products = pd.read_csv(raw / "olist_products_dataset.csv")
    trans = pd.read_csv(raw / "product_category_name_translation.csv")

    orders["order_purchase_timestamp"] = pd.to_datetime(
        orders["order_purchase_timestamp"], errors="coerce"
    )
    products = products.merge(
        trans.drop_duplicates("product_category_name"),
        on="product_category_name",
        how="left",
    )
    products["category"] = products["product_category_name_english"].fillna(
        products["product_category_name"]
    ).fillna("unknown")

    return orders, items, products


def calibrate_inc005(root, orders, items, products, profitability):
    month = pd.Timestamp("2017-09-01")
    mix = pd.read_csv(root / "data" / "synthetic" / "product_mix_overrides.csv")

    x = (
        items[["order_id", "product_id", "price"]]
        .merge(
            orders[["order_id", "order_purchase_timestamp"]],
            on="order_id",
            how="left",
        )
        .merge(products[["product_id", "category"]], on="product_id", how="left")
    )
    x["month"] = month_floor(x["order_purchase_timestamp"])
    x = x[x["month"] == month].copy()

    margins = profitability[["order_id", "revenue", "cogs"]].copy()
    margins["order_gross_margin_pct"] = (
        (margins["revenue"] - margins["cogs"]) /
        margins["revenue"].where(margins["revenue"] != 0)
    )
    x = x.merge(
        margins[["order_id", "order_gross_margin_pct"]],
        on="order_id",
        how="left",
    )

    x = x.merge(
        mix[["order_id", "category", "demand_weight_multiplier", "mix_override_reason"]],
        on=["order_id", "category"],
        how="left",
    )
    x["demand_weight_multiplier"] = x["demand_weight_multiplier"].fillna(1.0)
    x["mix_override_reason"] = x["mix_override_reason"].fillna("unchanged")

    x["baseline_revenue"] = x["price"].astype(float)
    x["baseline_cogs"] = (
        x["baseline_revenue"] * (1.0 - x["order_gross_margin_pct"])
    )
    x["effective_revenue"] = x["baseline_revenue"] * x["demand_weight_multiplier"]
    x["effective_cogs"] = x["baseline_cogs"] * x["demand_weight_multiplier"]
    x["baseline_gross_profit"] = x["baseline_revenue"] - x["baseline_cogs"]
    x["effective_gross_profit"] = x["effective_revenue"] - x["effective_cogs"]

    out_cols = [
        "order_id", "product_id", "category", "mix_override_reason",
        "demand_weight_multiplier", "baseline_revenue", "baseline_cogs",
        "baseline_gross_profit", "effective_revenue", "effective_cogs",
        "effective_gross_profit",
    ]
    x[out_cols].to_csv(
        root / "data" / "synthetic" / "inc005_effective_mix_economics.csv",
        index=False,
    )

    base_rev = x["baseline_revenue"].sum()
    eff_rev = x["effective_revenue"].sum()
    base_gp = x["baseline_gross_profit"].sum()
    eff_gp = x["effective_gross_profit"].sum()
    base_margin = base_gp / base_rev if base_rev else 0
    eff_margin = eff_gp / eff_rev if eff_rev else 0

    promoted = x[x["mix_override_reason"] == "mix_shift_toward_lower_margin"]
    base_share = promoted["baseline_revenue"].sum() / base_rev if base_rev else 0
    eff_share = promoted["effective_revenue"].sum() / eff_rev if eff_rev else 0

    return {
        "baseline_revenue": float(base_rev),
        "effective_revenue": float(eff_rev),
        "baseline_gross_margin": float(base_margin),
        "effective_gross_margin": float(eff_margin),
        "margin_change_pp": float((eff_margin - base_margin) * 100),
        "low_margin_share_baseline": float(base_share),
        "low_margin_share_effective": float(eff_share),
        "low_margin_share_change_pp": float((eff_share - base_share) * 100),
    }


def calibrate_inc006(root, profitability):
    month = pd.Timestamp("2017-11-01")
    econ = pd.read_csv(
        root / "data" / "synthetic" / "inc006_order_marketing_economics.csv"
    )

    m = profitability[profitability["month"] == month].copy()

    # Avoid collisions with baseline business-layer columns already present
    # in order_profitability.csv. Keep INC_006 economics explicitly namespaced.
    econ = econ.rename(columns={
        "allocated_marketing_cost": "inc006_allocated_marketing_cost",
        "campaign_incentive_cost": "inc006_campaign_incentive_cost",
        "campaign_id": "inc006_campaign_id",
        "incident_id": "inc006_incident_id",
        "source_type": "inc006_source_type",
    })

    m = m.merge(econ, on="order_id", how="left")

    m["inc006_allocated_marketing_cost"] = (
        m["inc006_allocated_marketing_cost"].fillna(0.0)
    )
    m["inc006_campaign_incentive_cost"] = (
        m["inc006_campaign_incentive_cost"].fillna(0.0)
    )
    m["is_campaign_attributed"] = m["inc006_campaign_id"].notna()

    # Controlled causal growth mechanism:
    # attributed orders receive a 12% incremental-revenue uplift.
    m["incremental_revenue"] = 0.0
    m.loc[m["is_campaign_attributed"], "incremental_revenue"] = (
        m.loc[m["is_campaign_attributed"], "revenue"] * 0.12
    )

    # Incremental revenue carries the same baseline COGS ratio as the order.
    cogs_ratio = (m["cogs"] / m["revenue"].where(m["revenue"] != 0)).fillna(0.0)
    m["incremental_cogs"] = m["incremental_revenue"] * cogs_ratio

    m["effective_revenue"] = m["revenue"] + m["incremental_revenue"]
    m["effective_cogs"] = m["cogs"] + m["incremental_cogs"]

    # Existing contribution profit already includes the normal business-layer economics.
    # Add campaign-driven economics on top for the controlled incident.
    m["effective_contribution_profit"] = (
        m["contribution_profit"]
        + m["incremental_revenue"]
        - m["incremental_cogs"]
        - m["inc006_allocated_marketing_cost"]
        - m["inc006_campaign_incentive_cost"]
    )

    cols = [
        "order_id", "revenue", "cogs", "contribution_profit",
        "is_campaign_attributed", "incremental_revenue", "incremental_cogs",
        "inc006_allocated_marketing_cost", "inc006_campaign_incentive_cost",
        "effective_revenue", "effective_cogs", "effective_contribution_profit",
    ]
    m[cols].to_csv(
        root / "data" / "synthetic" / "inc006_effective_marketing_economics.csv",
        index=False,
    )

    base_rev = m["revenue"].sum()
    eff_rev = m["effective_revenue"].sum()
    base_cp = m["contribution_profit"].sum()
    eff_cp = m["effective_contribution_profit"].sum()
    base_cm = base_cp / base_rev if base_rev else 0
    eff_cm = eff_cp / eff_rev if eff_rev else 0

    return {
        "baseline_revenue": float(base_rev),
        "effective_revenue": float(eff_rev),
        "revenue_growth_pct": float(eff_rev / base_rev - 1.0) if base_rev else 0,
        "baseline_contribution_profit": float(base_cp),
        "effective_contribution_profit": float(eff_cp),
        "contribution_profit_growth_pct": float(eff_cp / base_cp - 1.0) if base_cp else 0,
        "baseline_contribution_margin": float(base_cm),
        "effective_contribution_margin": float(eff_cm),
        "contribution_margin_change_pp": float((eff_cm - base_cm) * 100),
        "campaign_spend": float(m["inc006_allocated_marketing_cost"].sum()),
        "campaign_incentive_cost": float(m["inc006_campaign_incentive_cost"].sum()),
        "incremental_revenue": float(m["incremental_revenue"].sum()),
    }


def calibrate_inc007(root, orders, items, products):
    month = pd.Timestamp("2018-05-01")
    stock = pd.read_csv(root / "data" / "synthetic" / "stockout_events.csv")
    stock["stockout_start"] = pd.to_datetime(stock["stockout_start"])
    stock["stockout_end"] = pd.to_datetime(stock["stockout_end"])

    x = (
        items[["order_id", "product_id", "price"]]
        .merge(
            orders[["order_id", "order_purchase_timestamp"]],
            on="order_id",
            how="left",
        )
        .merge(products[["product_id", "category"]], on="product_id", how="left")
    )
    x["month"] = month_floor(x["order_purchase_timestamp"])
    x = x[x["month"] == month].copy()

    cfg = stock[[
        "product_id", "stockout_start", "stockout_end",
        "availability_multiplier"
    ]].copy()
    x = x.merge(cfg, on="product_id", how="left")

    in_window = (
        x["availability_multiplier"].notna()
        & (x["order_purchase_timestamp"] >= x["stockout_start"])
        & (x["order_purchase_timestamp"] <= x["stockout_end"] + pd.Timedelta(days=1))
    )

    x["recognized_revenue_multiplier"] = 1.0
    x.loc[in_window, "recognized_revenue_multiplier"] = (
        x.loc[in_window, "availability_multiplier"]
    )
    x["baseline_revenue"] = x["price"].astype(float)
    x["effective_revenue"] = (
        x["baseline_revenue"] * x["recognized_revenue_multiplier"]
    )
    x["modeled_lost_revenue"] = x["baseline_revenue"] - x["effective_revenue"]
    x["incident_id"] = pd.NA
    x.loc[in_window, "incident_id"] = "INC_007"

    x[[
        "order_id", "product_id", "category", "order_purchase_timestamp",
        "incident_id", "recognized_revenue_multiplier",
        "baseline_revenue", "effective_revenue", "modeled_lost_revenue",
    ]].to_csv(
        root / "data" / "synthetic" / "inc007_effective_sales.csv",
        index=False,
    )

    affected_category = stock["category"].iloc[0]
    cat = x[x["category"] == affected_category]
    affected = x[in_window]

    cat_base = cat["baseline_revenue"].sum()
    lost = affected["modeled_lost_revenue"].sum()

    return {
        "affected_category": affected_category,
        "affected_lines": int(in_window.sum()),
        "baseline_category_revenue": float(cat_base),
        "modeled_lost_revenue": float(lost),
        "modeled_category_revenue_loss_pct": float(lost / cat_base) if cat_base else 0,
        "average_recognized_multiplier_during_stockout": float(
            affected["recognized_revenue_multiplier"].mean()
        ) if len(affected) else 0,
    }


def calibrate_inc008(root):
    cx = pd.read_csv(root / "data" / "synthetic" / "cx_incident_overrides.csv")

    scored = cx.dropna(subset=["original_review_score"]).copy()
    base_avg = scored["original_review_score"].mean()
    eff_avg = scored["effective_review_score"].mean()

    base_negative = (scored["original_review_score"] <= 2).mean()
    eff_negative = (scored["effective_review_score"] <= 2).mean()

    return {
        "affected_orders": int(len(cx)),
        "average_added_delay_days": float(cx["extra_delivery_delay_days"].mean()),
        "baseline_avg_review_score": float(base_avg),
        "effective_avg_review_score": float(eff_avg),
        "review_score_change": float(eff_avg - base_avg),
        "baseline_negative_review_rate": float(base_negative),
        "effective_negative_review_rate": float(eff_negative),
        "negative_review_rate_change_pp": float((eff_negative - base_negative) * 100),
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--project-root", default=".")
    args = ap.parse_args()

    root = Path(args.project_root).resolve()
    (root / "docs").mkdir(parents=True, exist_ok=True)

    orders, items, products = load_raw(root)
    profitability = load_profitability(root)

    print("[1/4] Calibrating INC_005 business impact")
    i5 = calibrate_inc005(root, orders, items, products, profitability)
    print(
        f"      Gross margin: {i5['baseline_gross_margin']:.2%} -> "
        f"{i5['effective_gross_margin']:.2%} "
        f"({i5['margin_change_pp']:+.2f} pp)"
    )

    print("[2/4] Calibrating INC_006 business impact")
    i6 = calibrate_inc006(root, profitability)
    print(
        f"      Revenue growth={i6['revenue_growth_pct']:+.2%} | "
        f"Contribution profit growth={i6['contribution_profit_growth_pct']:+.2%} | "
        f"CM change={i6['contribution_margin_change_pp']:+.2f} pp"
    )

    print("[3/4] Calibrating INC_007 business impact")
    i7 = calibrate_inc007(root, orders, items, products)
    print(
        f"      Modeled category revenue loss="
        f"{i7['modeled_category_revenue_loss_pct']:.2%}"
    )

    print("[4/4] Calibrating INC_008 business impact")
    i8 = calibrate_inc008(root)
    print(
        f"      Review score: {i8['baseline_avg_review_score']:.2f} -> "
        f"{i8['effective_avg_review_score']:.2f} | "
        f"Avg added delay={i8['average_added_delay_days']:.2f} days"
    )

    report = {
        "INC_005": i5,
        "INC_006": i6,
        "INC_007": i7,
        "INC_008": i8,
    }

    (root / "docs" / "batch_b_business_impact_v3.json").write_text(
        json.dumps(report, indent=2), encoding="utf-8"
    )

    print("\nDone. Run audit_batch_b_business_impact_v3.py next.")


if __name__ == "__main__":
    main()
