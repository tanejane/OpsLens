
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import numpy as np
import pandas as pd


SEED = 20261025

# Explicitly isolated from frozen incidents:
# INC_002 = 2017-07, INC_003 = 2018-01, INC_001 = 2018-03, INC_004 = 2018-08
BATCH_B_MONTHS = {
    "INC_005": pd.Timestamp("2017-09-01"),
    "INC_006": pd.Timestamp("2017-11-01"),
    "INC_007": pd.Timestamp("2018-05-01"),
    "INC_008": pd.Timestamp("2018-06-01"),
}


def stable_u01(key: str, salt: str = "") -> float:
    h = hashlib.sha256(f"{salt}|{key}".encode("utf-8")).hexdigest()
    return int(h[:12], 16) / float(16**12 - 1)


def month_floor(s: pd.Series) -> pd.Series:
    return pd.to_datetime(s).dt.to_period("M").dt.to_timestamp()


def load_olist(root: Path):
    raw = root / "data" / "raw" / "olist"

    orders = pd.read_csv(raw / "olist_orders_dataset.csv")
    items = pd.read_csv(raw / "olist_order_items_dataset.csv")
    customers = pd.read_csv(raw / "olist_customers_dataset.csv")
    sellers = pd.read_csv(raw / "olist_sellers_dataset.csv")
    reviews = pd.read_csv(raw / "olist_order_reviews_dataset.csv")
    products = pd.read_csv(raw / "olist_products_dataset.csv")
    translation = pd.read_csv(raw / "product_category_name_translation.csv")

    for c in [
        "order_purchase_timestamp",
        "order_delivered_carrier_date",
        "order_delivered_customer_date",
        "order_estimated_delivery_date",
    ]:
        orders[c] = pd.to_datetime(orders[c], errors="coerce")

    reviews["review_creation_date"] = pd.to_datetime(
        reviews["review_creation_date"], errors="coerce"
    )

    products = products.merge(
        translation.drop_duplicates("product_category_name"),
        on="product_category_name",
        how="left",
    )
    products["category"] = products["product_category_name_english"].fillna(
        products["product_category_name"]
    ).fillna("unknown")

    return orders, items, customers, sellers, reviews, products


def ensure_months_exist(orders: pd.DataFrame):
    available_months = set(
        pd.to_datetime(orders["order_purchase_timestamp"], errors="coerce")
        .dropna()
        .dt.to_period("M")
        .astype(str)
        .unique()
    )

    for inc, month in BATCH_B_MONTHS.items():
        month_key = pd.Timestamp(month).to_period("M").strftime("%Y-%m")
        if month_key not in available_months:
            raise RuntimeError(
                f"{inc} assigned month {month_key} not present in Olist data. "
                f"Available range: {min(available_months)} to {max(available_months)}"
            )


def load_profitability(root: Path) -> pd.DataFrame:
    path = root / "data" / "processed" / "order_profitability.csv"
    if not path.exists():
        raise FileNotFoundError(
            "order_profitability.csv not found. Run the business-layer generator first."
        )
    df = pd.read_csv(path)
    df["order_purchase_timestamp"] = pd.to_datetime(
        df["order_purchase_timestamp"], errors="coerce"
    )
    df["month"] = month_floor(df["order_purchase_timestamp"])
    return df


def generate_inc005(root, orders, items, products, profitability):
    """
    Product-mix margin dilution:
    create an explicit effective product-mix view where a larger share of recognized
    demand in one month shifts toward naturally lower-margin categories.
    """
    month = BATCH_B_MONTHS["INC_005"]

    item = (
        items.merge(
            orders[["order_id", "order_purchase_timestamp"]],
            on="order_id",
            how="left",
        )
        .merge(
            products[["product_id", "category"]],
            on="product_id",
            how="left",
        )
    )
    item["month"] = month_floor(item["order_purchase_timestamp"])

    prof = profitability[["order_id", "gross_margin_pct"]].copy()
    item = item.merge(prof, on="order_id", how="left")

    cat_margin = (
        item[item["month"] < month]
        .groupby("category", as_index=False)
        .agg(
            median_margin=("gross_margin_pct", "median"),
            lines=("order_id", "count"),
        )
    )
    eligible = cat_margin[cat_margin["lines"] >= 100].sort_values("median_margin")

    if len(eligible) < 4:
        raise RuntimeError("Not enough categories to create a robust mix-shift incident.")

    low_margin = eligible.head(3)["category"].tolist()
    high_margin = eligible.tail(3)["category"].tolist()

    current = item[item["month"] == month].copy()

    # Create an analytical weighting override, not fake raw orders.
    # Lower-margin categories receive higher effective demand weights;
    # higher-margin categories receive lower weights.
    rows = []
    for r in current[["order_id", "category"]].drop_duplicates().itertuples(index=False):
        if r.category in low_margin:
            multiplier = 1.28
            reason = "mix_shift_toward_lower_margin"
        elif r.category in high_margin:
            multiplier = 0.82
            reason = "mix_shift_away_from_higher_margin"
        else:
            multiplier = 1.0
            reason = "unchanged"

        rows.append({
            "order_id": r.order_id,
            "incident_id": "INC_005",
            "incident_month": month.date(),
            "category": r.category,
            "demand_weight_multiplier": multiplier,
            "mix_override_reason": reason,
            "source_type": "controlled_synthetic_mix_override",
        })

    overrides = pd.DataFrame(rows)
    overrides.to_csv(
        root / "data" / "synthetic" / "product_mix_overrides.csv",
        index=False,
    )

    truth = {
        "incident_id": "INC_005",
        "name": "Margin Dilution From Product Mix",
        "incident_month": str(month.date()),
        "low_margin_categories_promoted": low_margin,
        "high_margin_categories_deemphasized": high_margin,
        "true_causes": [
            {
                "cause": "mix_shift_to_lower_margin_categories",
                "importance": "primary",
                "mechanism": "effective demand weighting rises 28% for low-margin categories and falls 18% for high-margin categories",
            }
        ],
        "decoys": [
            "broad_supplier_cost_increase",
            "across_the_board_price_cut",
        ],
        "required_evidence": [
            "product_mix_overrides",
            "order_items",
            "products",
            "order_profitability",
        ],
        "status": "IMPLEMENTED",
    }
    (root / "data" / "eval_ground_truth" / "incident_005.json").write_text(
        json.dumps(truth, indent=2), encoding="utf-8"
    )
    return truth


def generate_inc006(root, orders, profitability):
    """
    Unprofitable marketing growth:
    create a separate campaign that drives attributed revenue but carries enough
    acquisition cost + incentive cost to dilute contribution margin.
    """
    month = BATCH_B_MONTHS["INC_006"]

    m = profitability[profitability["month"] == month].copy()
    if len(m) < 1000:
        raise RuntimeError("INC_006 month has insufficient order volume.")

    m = m.sort_values("revenue", ascending=False)

    attributed = []
    for r in m.itertuples(index=False):
        if stable_u01(r.order_id, "inc006_attr") < 0.20:
            attributed.append(r.order_id)

    if len(attributed) < 100:
        raise RuntimeError("INC_006 generated too few attributed orders.")

    campaign = pd.DataFrame([{
        "campaign_id": "CMP_EFFICIENCY_01",
        "campaign_name": "ScaleNow Acquisition Push",
        "incident_id": "INC_006",
        "start_date": month.date(),
        "end_date": (month + pd.offsets.MonthEnd(0)).date(),
        "channel": "paid_social",
        "objective": "revenue_growth",
        "planned_budget": 62000.0,
        "campaign_incentive_rate": 0.04,
        "source_type": "controlled_synthetic_campaign",
    }])
    campaign.to_csv(
        root / "data" / "synthetic" / "inc006_campaign.csv",
        index=False,
    )

    total_weight = sum(
        max(float(m.loc[m["order_id"] == oid, "revenue"].iloc[0]), 1.0)
        for oid in attributed
    )

    rows = []
    for oid in attributed:
        revenue = float(m.loc[m["order_id"] == oid, "revenue"].iloc[0])
        spend_alloc = 62000.0 * max(revenue, 1.0) / total_weight
        incentive = revenue * 0.04

        rows.append({
            "order_id": oid,
            "incident_id": "INC_006",
            "campaign_id": "CMP_EFFICIENCY_01",
            "allocated_marketing_cost": round(spend_alloc, 4),
            "campaign_incentive_cost": round(incentive, 4),
            "source_type": "controlled_synthetic_marketing_economics",
        })

    econ = pd.DataFrame(rows)
    econ.to_csv(
        root / "data" / "synthetic" / "inc006_order_marketing_economics.csv",
        index=False,
    )

    truth = {
        "incident_id": "INC_006",
        "name": "Unprofitable Marketing Growth",
        "incident_month": str(month.date()),
        "campaign_id": "CMP_EFFICIENCY_01",
        "attributed_orders": int(len(econ)),
        "true_causes": [
            {
                "cause": "paid_acquisition_cost_growth",
                "importance": "primary",
                "mechanism": "62k campaign spend allocated to attributed orders",
            },
            {
                "cause": "campaign_incentive_cost",
                "importance": "secondary",
                "mechanism": "4% merchant-funded incentive on attributed revenue",
            },
        ],
        "decoys": [
            "campaign_generated_no_revenue",
            "returns_are_primary",
        ],
        "required_evidence": [
            "inc006_campaign",
            "inc006_order_marketing_economics",
            "order_profitability",
        ],
        "status": "IMPLEMENTED",
    }
    (root / "data" / "eval_ground_truth" / "incident_006.json").write_text(
        json.dumps(truth, indent=2), encoding="utf-8"
    )
    return truth


def generate_inc007(root, orders, items, products):
    """
    Stockout revenue loss:
    identify strong products and create a stock-availability override that makes
    selected high-demand SKUs unavailable for part of the month.
    """
    month = BATCH_B_MONTHS["INC_007"]

    x = (
        items.merge(
            orders[["order_id", "order_purchase_timestamp"]],
            on="order_id",
            how="left",
        )
        .merge(
            products[["product_id", "category"]],
            on="product_id",
            how="left",
        )
    )
    x["month"] = month_floor(x["order_purchase_timestamp"])

    history = x[x["month"] < month]
    product_rank = (
        history.groupby(["product_id", "category"], as_index=False)
        .agg(
            historical_lines=("order_id", "count"),
            historical_revenue=("price", "sum"),
        )
    )
    product_rank = product_rank[product_rank["historical_lines"] >= 20]
    product_rank = product_rank.sort_values("historical_revenue", ascending=False)

    # Pick a category with at least 3 strong SKUs.
    chosen_category = None
    chosen_products = None
    for cat, g in product_rank.groupby("category"):
        top = g.head(5)
        if len(top) >= 3:
            score = top["historical_revenue"].sum()
            if chosen_category is None or score > chosen_products["historical_revenue"].sum():
                chosen_category = cat
                chosen_products = top

    if chosen_products is None:
        raise RuntimeError("Could not find suitable products for stockout incident.")

    affected_products = chosen_products.head(3)["product_id"].tolist()

    stock_rows = []
    for pid in affected_products:
        stock_rows.append({
            "incident_id": "INC_007",
            "product_id": pid,
            "category": chosen_category,
            "incident_month": month.date(),
            "stockout_start": (month + pd.Timedelta(days=8)).date(),
            "stockout_end": (month + pd.Timedelta(days=20)).date(),
            "availability_multiplier": 0.15,
            "source_type": "controlled_synthetic_stockout_event",
        })

    stock = pd.DataFrame(stock_rows)
    stock.to_csv(
        root / "data" / "synthetic" / "stockout_events.csv",
        index=False,
    )

    truth = {
        "incident_id": "INC_007",
        "name": "Stockout Revenue Loss",
        "incident_month": str(month.date()),
        "affected_category": chosen_category,
        "affected_products": affected_products,
        "true_causes": [
            {
                "cause": "stockout_of_top_selling_products",
                "importance": "primary",
                "mechanism": "availability falls to 15% for three historically strong products during a 13-day window",
            }
        ],
        "decoys": [
            "customer_demand_collapse",
            "seller_price_increase",
        ],
        "required_evidence": [
            "stockout_events",
            "inventory_weekly",
            "order_items",
            "products",
        ],
        "status": "IMPLEMENTED",
    }
    (root / "data" / "eval_ground_truth" / "incident_007.json").write_text(
        json.dumps(truth, indent=2), encoding="utf-8"
    )
    return truth


def generate_inc008(root, orders, items, reviews):
    """
    CX decline:
    create an effective CX layer where a seller cluster experiences delivery
    deterioration and corresponding review-score pressure.
    """
    month = BATCH_B_MONTHS["INC_008"]

    x = items[["order_id", "seller_id"]].merge(
        orders[
            [
                "order_id",
                "order_purchase_timestamp",
                "order_delivered_customer_date",
                "order_estimated_delivery_date",
            ]
        ],
        on="order_id",
        how="left",
    )
    x["month"] = month_floor(x["order_purchase_timestamp"])

    m = x[
        (x["month"] == month)
        & x["order_delivered_customer_date"].notna()
    ].copy()

    top_sellers = (
        m.groupby("seller_id")["order_id"]
        .nunique()
        .sort_values(ascending=False)
        .head(2)
        .index.tolist()
    )

    affected_orders = (
        m[m["seller_id"].isin(top_sellers)]["order_id"]
        .drop_duplicates()
        .tolist()
    )

    base_reviews = (
        reviews.sort_values("review_creation_date")
        .groupby("order_id", as_index=False)
        .agg(review_score=("review_score", "mean"))
    )
    review_map = base_reviews.set_index("order_id")["review_score"].to_dict()

    rows = []
    for oid in affected_orders:
        if stable_u01(oid, "inc008_apply") < 0.45:
            original = review_map.get(oid, np.nan)
            effective_score = (
                max(1.0, float(original) - 1.5)
                if pd.notna(original)
                else 2.5
            )
            rows.append({
                "order_id": oid,
                "incident_id": "INC_008",
                "extra_delivery_delay_days": 3 + int(4 * stable_u01(oid, "inc008_delay")),
                "original_review_score": original,
                "effective_review_score": round(effective_score, 2),
                "source_type": "controlled_synthetic_cx_event",
            })

    cx = pd.DataFrame(rows)
    if len(cx) < 20:
        raise RuntimeError("INC_008 generated too few CX-affected orders.")

    cx.to_csv(
        root / "data" / "synthetic" / "cx_incident_overrides.csv",
        index=False,
    )

    truth = {
        "incident_id": "INC_008",
        "name": "Customer Experience Decline",
        "incident_month": str(month.date()),
        "affected_sellers": top_sellers,
        "affected_orders": int(len(cx)),
        "true_causes": [
            {
                "cause": "late_delivery_concentration",
                "importance": "primary",
            },
            {
                "cause": "specific_seller_quality_issue",
                "importance": "secondary",
            },
        ],
        "decoys": [
            "product_category_mix_alone",
            "payment_method_mix",
        ],
        "required_evidence": [
            "cx_incident_overrides",
            "orders",
            "reviews",
            "sellers",
        ],
        "status": "IMPLEMENTED",
    }
    (root / "data" / "eval_ground_truth" / "incident_008.json").write_text(
        json.dumps(truth, indent=2), encoding="utf-8"
    )
    return truth


def update_catalog(root: Path, truths: list[dict]):
    path = root / "data" / "eval_ground_truth" / "incident_catalog_v1.json"
    if not path.exists():
        return

    catalog = json.loads(path.read_text(encoding="utf-8"))
    truth_by_id = {t["incident_id"]: t for t in truths}

    for item in catalog:
        if item["incident_id"] in truth_by_id:
            item["status"] = "IMPLEMENTED"

    path.write_text(json.dumps(catalog, indent=2), encoding="utf-8")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--project-root", default=".")
    args = ap.parse_args()

    root = Path(args.project_root).resolve()
    (root / "data" / "synthetic").mkdir(parents=True, exist_ok=True)
    (root / "data" / "eval_ground_truth").mkdir(parents=True, exist_ok=True)

    orders, items, customers, sellers, reviews, products = load_olist(root)
    ensure_months_exist(orders)
    profitability = load_profitability(root)

    print("[1/5] INC_005 Product-mix margin dilution")
    t5 = generate_inc005(root, orders, items, products, profitability)
    print(f"      Month={t5['incident_month']}")

    print("[2/5] INC_006 Unprofitable marketing growth")
    t6 = generate_inc006(root, orders, profitability)
    print(
        f"      Month={t6['incident_month']} "
        f"Attributed orders={t6['attributed_orders']}"
    )

    print("[3/5] INC_007 Stockout revenue loss")
    t7 = generate_inc007(root, orders, items, products)
    print(
        f"      Month={t7['incident_month']} "
        f"Category={t7['affected_category']}"
    )

    print("[4/5] INC_008 Customer-experience decline")
    t8 = generate_inc008(root, orders, items, reviews)
    print(
        f"      Month={t8['incident_month']} "
        f"Affected orders={t8['affected_orders']}"
    )

    print("[5/5] Updating incident catalog")
    update_catalog(root, [t5, t6, t7, t8])

    month_map = {
        **{
            "INC_001": "2018-03-01",
            "INC_002": "2017-07-01",
            "INC_003": "2018-01-01",
            "INC_004": "2018-08-01",
        },
        **{
            k: str(v.date())
            for k, v in BATCH_B_MONTHS.items()
        },
    }
    (root / "data" / "eval_ground_truth" / "all_incident_months_v1.json").write_text(
        json.dumps(month_map, indent=2), encoding="utf-8"
    )

    print("\nDone. Run audit_batch_b_incidents.py next.")


if __name__ == "__main__":
    main()
