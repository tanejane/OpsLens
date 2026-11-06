from __future__ import annotations



import argparse

import hashlib

import json

from pathlib import Path



import pandas as pd





SEED = 20261025



def load_incident_months(root: Path):

    path = root / "data" / "eval_ground_truth" / "incident_month_assignments.json"

    return {

        k: pd.Timestamp(v)

        for k, v in json.loads(path.read_text(encoding="utf-8")).items()

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





def choose_mature_month(orders: pd.DataFrame, min_orders: int = 4000) -> pd.Timestamp:

    x = orders.copy()

    x["month"] = month_floor(x["order_purchase_timestamp"])



    monthly = (

        x.groupby("month")["order_id"]

        .nunique()

        .sort_index()

    )
# Exclude first 2 and last 2 calendar months to avoid dataset truncation/launch tails.

    valid = monthly.iloc[2:-2]

    valid = valid[valid >= min_orders]



    if valid.empty:

        raise RuntimeError("No mature month found for controlled incidents.")
# Pick a middle mature month deterministically, not the single highest-volume month.

    return pd.Timestamp(valid.index[len(valid) // 2])





def generate_inc002(root, orders, items, customers, incident_month):

    """

    Controlled regional capacity disruption.



    Unlike v1, this does NOT claim an existing decline was caused by a synthetic event.

    It selects a mature real month, then creates an explicit order-level operational

    override layer. The future canonical business view will apply these overrides.

    """

    month = pd.Timestamp(incident_month)



    base = (

        orders[["order_id", "customer_id", "order_purchase_timestamp", "order_status"]]

        .merge(customers[["customer_id", "customer_state"]], on="customer_id", how="left")

        .merge(

            items.groupby("order_id", as_index=False)["price"].sum()

            .rename(columns={"price": "observed_item_revenue"}),

            on="order_id",

            how="left",

        )

    )

    base["month"] = month_floor(base["order_purchase_timestamp"])



    month_state = (

        base[base["month"] == month]

        .groupby("customer_state", as_index=False)

        .agg(

            orders=("order_id", "nunique"),

            revenue=("observed_item_revenue", "sum"),

        )

        .sort_values("revenue", ascending=False)

    )
# Pick a major region with enough volume, excluding SP to avoid making the case too obvious.

    candidates = month_state[

        (month_state["orders"] >= 300)

        & (month_state["customer_state"] != "SP")

    ]

    if candidates.empty:

        candidates = month_state[month_state["orders"] >= 200]



    state = candidates.iloc[0]["customer_state"]



    affected_orders = base[

        (base["month"] == month)

        & (base["customer_state"] == state)

        & (base["order_status"].isin(["delivered", "shipped", "invoiced", "processing"]))

    ].copy()



    rows = []

    for r in affected_orders.itertuples(index=False):

        u = stable_u01(r.order_id, "inc002_capacity")

        if u < 0.16:

            rows.append({

                "order_id": r.order_id,

                "incident_id": "INC_002",

                "customer_state": state,

                "incident_month": month.date(),

                "capacity_impact": "lost_order_capacity",

                "recognized_revenue_multiplier": 0.0,

                "extra_delivery_delay_days": 0,

                "source_type": "controlled_synthetic_operational_override",

            })

        elif u < 0.34:

            rows.append({

                "order_id": r.order_id,

                "incident_id": "INC_002",

                "customer_state": state,

                "incident_month": month.date(),

                "capacity_impact": "delayed_fulfillment",

                "recognized_revenue_multiplier": 1.0,

                "extra_delivery_delay_days": 3 + int(4 * stable_u01(r.order_id, "inc002_delay")),

                "source_type": "controlled_synthetic_operational_override",

            })



    overrides = pd.DataFrame(rows)

    if overrides.empty:

        raise RuntimeError("INC_002 unexpectedly produced no operational overrides.")



    overrides.to_csv(

        root / "data" / "synthetic" / "regional_capacity_overrides.csv",

        index=False,

    )



    lost = overrides[overrides["recognized_revenue_multiplier"] == 0.0]

    impacted_ids = set(lost["order_id"])

    lost_revenue = float(

        affected_orders[affected_orders["order_id"].isin(impacted_ids)][

            "observed_item_revenue"

        ].sum()

    )

    base_region_revenue = float(affected_orders["observed_item_revenue"].sum())

    modeled_decline = lost_revenue / base_region_revenue if base_region_revenue else 0.0



    truth = {

        "incident_id": "INC_002",

        "name": "Regional Capacity Disruption",

        "incident_month": str(month.date()),

        "affected_state": state,

        "modeled_revenue_loss_pct": modeled_decline,

        "true_causes": [

            {

                "cause": "regional_seller_capacity_disruption",

                "importance": "primary",

                "mechanism": "16% of eligible regional orders lose recognized revenue in the controlled business view",

            },

            {

                "cause": "regional_fulfillment_delay",

                "importance": "secondary",

                "mechanism": "additional regional orders receive 3–6 day fulfillment delays",

            },

        ],

        "decoys": [

            "national_demand_collapse",

            "payment_failure_spike",

        ],

        "required_evidence": [

            "regional_capacity_overrides",

            "orders",

            "order_items",

            "customers",

        ],

        "status": "IMPLEMENTED_V2",

    }

    (root / "data" / "eval_ground_truth" / "incident_002.json").write_text(

        json.dumps(truth, indent=2), encoding="utf-8"

    )

    return truth





def generate_inc003(root, orders, items, products, incident_month):

    """

    Controlled product-quality event that materially increases returns for two

    high-volume SKUs belonging to one seller.

    """

    month = pd.Timestamp(incident_month)



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



    m = x[x["month"] == month].copy()

    pair_counts = (

        m.groupby(["seller_id", "product_id"])

        .size()

        .reset_index(name="lines")

        .sort_values("lines", ascending=False)

    )



    seller_totals = (

        pair_counts.groupby("seller_id")["lines"]

        .sum()

        .sort_values(ascending=False)

    )



    seller_id = None

    skus = None

    for sid in seller_totals.index:

        p = pair_counts[pair_counts["seller_id"] == sid].head(2)

        if len(p) == 2 and p["lines"].min() >= 6:

            seller_id = sid

            skus = p["product_id"].tolist()

            break



    if seller_id is None:

        raise RuntimeError("Could not find a seller with two suitable high-volume SKUs.")



    target_orders = (

        m[

            (m["seller_id"] == seller_id)

            & (m["product_id"].isin(skus))

        ]["order_id"]

        .drop_duplicates()

        .tolist()

    )



    existing_path = root / "data" / "synthetic" / "returns.csv"

    if existing_path.exists():

        returns = pd.read_csv(existing_path)
# Remove prior INC003 records to keep reruns idempotent.

        if "source_type" in returns.columns:

            returns = returns[

                returns["source_type"] != "controlled_synthetic_defect_incident"

            ].copy()

    else:

        returns = pd.DataFrame(

            columns=[

                "return_id", "order_id", "return_reason",

                "refund_amount", "return_date", "source_type"

            ]

        )



    order_values = (

        items.groupby("order_id", as_index=False)["price"].sum()

        .rename(columns={"price": "order_value"})

        .set_index("order_id")["order_value"]

        .to_dict()

    )



    extra = []

    for oid in target_orders:

        if stable_u01(oid, "inc003_return") < 0.34:

            extra.append({

                "return_id": f"INC003_{oid[:12]}",

                "order_id": oid,

                "return_reason": "damaged_or_defective",

                "refund_amount": round(float(order_values.get(oid, 0.0)) * 0.85, 2),

                "return_date": str((month + pd.offsets.MonthEnd(0)).date()),

                "source_type": "controlled_synthetic_defect_incident",

            })



    if len(extra) < 3:

        raise RuntimeError("INC_003 generated too few defect returns.")



    pd.concat([returns, pd.DataFrame(extra)], ignore_index=True).to_csv(

        existing_path, index=False

    )



    quality = pd.DataFrame([

        {

            "incident_id": "INC_003",

            "seller_id": seller_id,

            "product_id": pid,

            "incident_month": month.date(),

            "quality_issue": "damage_or_defect_rate_spike",

            "modeled_incident_return_rate": 0.34,

            "source_type": "controlled_synthetic_quality_event",

        }

        for pid in skus

    ])

    quality.to_csv(

        root / "data" / "synthetic" / "product_quality_events.csv",

        index=False,

    )



    truth = {

        "incident_id": "INC_003",

        "name": "Returns Spike",

        "incident_month": str(month.date()),

        "affected_seller": seller_id,

        "affected_products": skus,

        "injected_return_count": len(extra),

        "true_causes": [

            {"cause": "defect_rate_spike_in_two_skus", "importance": "primary"},

            {"cause": "single_seller_concentration", "importance": "secondary"},

        ],

        "decoys": [

            "all_categories_affected",

            "late_delivery_is_primary",

        ],

        "required_evidence": [

            "returns",

            "product_quality_events",

            "products",

            "sellers",

            "order_items",

        ],

        "status": "IMPLEMENTED_V2",

    }

    (root / "data" / "eval_ground_truth" / "incident_003.json").write_text(

        json.dumps(truth, indent=2), encoding="utf-8"

    )

    return truth





def generate_inc004(root, orders, items, incident_month):

    """

    Controlled delivery deterioration. Creates an EFFECTIVE delivery table with

    adjusted timestamps instead of merely attaching an event label.

    """

    month = pd.Timestamp(incident_month)



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

        .head(3)

        .index.tolist()

    )



    target_orders = (

        m[m["seller_id"].isin(top_sellers)]["order_id"]

        .drop_duplicates()

        .tolist()

    )



    effective = orders[

        [

            "order_id",

            "order_delivered_customer_date",

            "order_estimated_delivery_date",

        ]

    ].copy()



    effective["effective_delivered_customer_date"] = pd.to_datetime(

        effective["order_delivered_customer_date"], errors="coerce"

    )

    effective["incident_id"] = pd.NA

    effective["extra_delay_days"] = 0



    target_set = set(target_orders)

    for i, r in effective.iterrows():

        oid = r["order_id"]

        if oid not in target_set:

            continue

        if stable_u01(oid, "inc004_apply") < 0.42:

            extra = 4 + int(5 * stable_u01(oid, "inc004_delay"))

            effective.at[i, "effective_delivered_customer_date"] = (

                pd.Timestamp(r["order_delivered_customer_date"])

                + pd.Timedelta(days=extra)

            )

            effective.at[i, "incident_id"] = "INC_004"

            effective.at[i, "extra_delay_days"] = extra



    effective["effective_late_days"] = (

        pd.to_datetime(effective["effective_delivered_customer_date"])

        - pd.to_datetime(effective["order_estimated_delivery_date"])

    ).dt.total_seconds() / 86400

    effective["effective_is_late"] = (

        effective["effective_late_days"] > 0

    ).astype("Int64")



    impacted = effective[effective["incident_id"] == "INC_004"]

    if len(impacted) < 10:

        raise RuntimeError("INC_004 generated too few delayed orders.")



    effective.to_csv(

        root / "data" / "synthetic" / "effective_delivery_dates.csv",

        index=False,

    )



    truth = {

        "incident_id": "INC_004",

        "name": "Delivery Deterioration",

        "incident_month": str(month.date()),

        "affected_sellers": top_sellers,

        "delayed_order_count": int(len(impacted)),

        "true_causes": [

            {"cause": "carrier_handoff_delay", "importance": "primary"},

            {"cause": "specific_seller_cluster", "importance": "secondary"},

        ],

        "decoys": [

            "all_sellers_deteriorated",

            "customer_geography_alone_explains_issue",

        ],

        "required_evidence": [

            "effective_delivery_dates",

            "orders",

            "sellers",

            "reviews",

        ],

        "status": "IMPLEMENTED_V2",

    }

    (root / "data" / "eval_ground_truth" / "incident_004.json").write_text(

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

            item["status"] = "IMPLEMENTED_V2"

    path.write_text(json.dumps(catalog, indent=2), encoding="utf-8")





def main():

    ap = argparse.ArgumentParser()

    ap.add_argument("--project-root", default=".")

    args = ap.parse_args()



    root = Path(args.project_root).resolve()

    (root / "data" / "synthetic").mkdir(parents=True, exist_ok=True)

    (root / "data" / "eval_ground_truth").mkdir(parents=True, exist_ok=True)



    orders, items, customers, sellers, reviews, products = load_olist(root)
    incident_months = load_incident_months(root)

    required_incidents = ["INC_002", "INC_003", "INC_004"]
    missing_assignments = [k for k in required_incidents if k not in incident_months]
    if missing_assignments:
        raise RuntimeError(
            f"Missing incident month assignments: {missing_assignments}"
        )

    assigned = [incident_months[k] for k in required_incidents]
    if len(set(assigned)) != len(assigned):
        raise RuntimeError(
            "INC_002, INC_003 and INC_004 must use different incident months."
        )

    if pd.Timestamp("2018-03-01") in assigned:
        raise RuntimeError(
            "INC_002–INC_004 must not overlap frozen INC_001 (2018-03-01)."
        )



    print("[1/4] Implementing INC_002 causal regional capacity disruption")

    t2 = generate_inc002(
        root,
        orders,
        items,
        customers,
        incident_months["INC_002"],
    )

    print(

        f"      State={t2['affected_state']} Month={t2['incident_month']} "

        f"Modeled revenue loss={t2['modeled_revenue_loss_pct']:.2%}"

    )



    print("[2/4] Implementing INC_003 controlled quality/returns event")

    t3 = generate_inc003(
        root,
        orders,
        items,
        products,
        incident_months["INC_003"],
    )

    print(

        f"      Month={t3['incident_month']} "

        f"Injected returns={t3['injected_return_count']}"

    )



    print("[3/4] Implementing INC_004 effective delivery deterioration")

    t4 = generate_inc004(
        root,
        orders,
        items,
        incident_months["INC_004"],
    )

    print(

        f"      Month={t4['incident_month']} "

        f"Delayed orders={t4['delayed_order_count']}"

    )



    print("[4/4] Updating incident catalog")

    update_catalog(root, [t2, t3, t4])



    print("\nDone. Run audit_batch_a_incidents_v2.py next.")





if __name__ == "__main__":

    main()