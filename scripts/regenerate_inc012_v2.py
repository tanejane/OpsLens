
from __future__ import annotations

import argparse
import json
from pathlib import Path

import pandas as pd


def build_rows():
    """
    Construct a clean Simpson's-paradox/confounding fixture.

    Within each order-value band, promo exposure has the SAME refund rate.
    But promo exposure is much more common in the high-value band, which has
    a higher baseline refund rate. Therefore the aggregate promo group appears
    to refund more often even though promo itself has no within-band effect.

    High-value:
      promo:     160 orders, 20 refunds = 12.5%
      non-promo:  40 orders,  5 refunds = 12.5%

    Low-value:
      promo:      60 orders,  2 refunds = 3.33%
      non-promo: 240 orders,  8 refunds = 3.33%

    Aggregate:
      promo:     22 / 220 = 10.00%
      non-promo: 13 / 280 = 4.64%
    """
    rows = []
    idx = 0

    groups = [
        ("high", 1, 160, 20, 240.0),
        ("high", 0, 40, 5, 240.0),
        ("low", 1, 60, 2, 65.0),
        ("low", 0, 240, 8, 65.0),
    ]

    for band, promo, n, refunds, base_value in groups:
        for j in range(n):
            rows.append({
                "synthetic_order_id": f"INC012_{idx:04d}",
                "incident_id": "INC_012",
                "promo_exposed": promo,
                "order_value_band": band,
                "order_value": base_value + (j % 20),
                "did_refund": 1 if j < refunds else 0,
            })
            idx += 1

    return pd.DataFrame(rows)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--project-root", default=".")
    args = ap.parse_args()

    root = Path(args.project_root).resolve()
    synth = root / "data" / "synthetic"
    truth_dir = root / "data" / "eval_ground_truth"
    synth.mkdir(parents=True, exist_ok=True)
    truth_dir.mkdir(parents=True, exist_ok=True)

    df = build_rows()
    out_path = synth / "inc012_misleading_correlation.csv"
    df.to_csv(out_path, index=False)

    overall = (
        df.groupby("promo_exposed")["did_refund"]
        .mean()
        .to_dict()
    )

    subgroup = (
        df.groupby(["order_value_band", "promo_exposed"])["did_refund"]
        .mean()
        .reset_index()
        .to_dict(orient="records")
    )

    truth = {
        "incident_id": "INC_012",
        "name": "Misleading Correlation",
        "incident_month": "2018-07-01",
        "apparent_relationship": {
            "promo_refund_rate": {
                str(k): float(v) for k, v in overall.items()
            }
        },
        "true_explanation": "order_value_mix_confounding",
        "subgroup_refund_rates": subgroup,
        "causal_structure": {
            "order_value_band_affects_promo_exposure": True,
            "order_value_band_affects_refund_risk": True,
            "promo_has_within_band_refund_effect": False
        },
        "expected_agent_behavior": [
            "identify aggregate association",
            "avoid causal claim from aggregate correlation",
            "segment by order value",
            "compare promo and non-promo refund rates within strata",
            "reject promotion-as-primary-cause",
            "identify order-value mix as the confounder",
        ],
        "status": "IMPLEMENTED_V2",
    }

    truth_path = truth_dir / "incident_012.json"
    truth_path.write_text(json.dumps(truth, indent=2), encoding="utf-8")

    print("INC_012 regenerated as clean confounding fixture.")
    print(
        f"Overall refund rate: promo={overall[1]:.2%}, "
        f"non-promo={overall[0]:.2%}"
    )

    subgroup_df = (
        df.groupby(["order_value_band", "promo_exposed"])["did_refund"]
        .mean()
        .unstack()
    )
    for band in subgroup_df.index:
        print(
            f"{band}: promo={subgroup_df.loc[band, 1]:.2%}, "
            f"non-promo={subgroup_df.loc[band, 0]:.2%}"
        )

    print(f"Saved: {out_path}")
    print(f"Updated: {truth_path}")


if __name__ == "__main__":
    main()
