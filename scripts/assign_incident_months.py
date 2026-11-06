
from __future__ import annotations

import argparse
import json
from pathlib import Path
import pandas as pd


def month_floor(s):
    return pd.to_datetime(s).dt.to_period("M").dt.to_timestamp()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--project-root", default=".")
    args = ap.parse_args()

    root = Path(args.project_root).resolve()
    raw = root / "data" / "raw" / "olist"

    orders = pd.read_csv(raw / "olist_orders_dataset.csv")
    orders["order_purchase_timestamp"] = pd.to_datetime(
        orders["order_purchase_timestamp"], errors="coerce"
    )
    orders["month"] = month_floor(orders["order_purchase_timestamp"])

    monthly = (
        orders.groupby("month")["order_id"]
        .nunique()
        .sort_index()
    )

    # Exclude weak boundary months and keep mature periods only.
    mature = monthly.iloc[2:-2]
    mature = mature[mature >= 4000]

    if len(mature) < 4:
        raise RuntimeError("Not enough mature months to isolate incidents.")

    # Keep INC_001 = 2018-03 if present. Select three other mature months.
    excluded = {pd.Timestamp("2018-03-01")}
    candidates = [pd.Timestamp(m) for m in mature.index if pd.Timestamp(m) not in excluded]

    # Spread incidents across the timeline.
    pick_idx = [0, len(candidates)//2, len(candidates)-1]
    picks = [candidates[i] for i in pick_idx]

    mapping = {
        "INC_002": picks[0],
        "INC_003": picks[1],
        "INC_004": picks[2],
    }

    # Save explicit month assignment used by future generators.
    config = {
        inc: str(month.date())
        for inc, month in mapping.items()
    }

    path = root / "data" / "eval_ground_truth" / "incident_month_assignments.json"
    path.write_text(json.dumps(config, indent=2), encoding="utf-8")

    print("Assigned isolated months:")
    for inc, month in mapping.items():
        print(f"  {inc}: {month.date()}")

    print("\nSaved:")
    print(path)
    print("\nNext: update Batch A v2 generator to read these month assignments.")


if __name__ == "__main__":
    main()
