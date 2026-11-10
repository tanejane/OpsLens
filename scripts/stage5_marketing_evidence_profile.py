"""Stage 5: descriptive marketing evidence profiling.

Offline only. Does not claim campaign incrementality or independent
mechanism verification. Does not execute MCP, SQL, or Gemini.
"""
import csv
import json
from collections import defaultdict
from datetime import date
from decimal import Decimal, InvalidOperation
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
INPUT = ROOT / "data" / "synthetic" / "marketing_spend_daily.csv"
OUTPUT = ROOT / "reports" / "stage5_marketing_evidence_profile.json"
MONTHS = ("2018-02", "2018-03")


def main():
    if not INPUT.is_file():
        raise SystemExit(f"Missing source: {INPUT}")

    totals = defaultdict(lambda: Decimal("0"))
    by_campaign = defaultdict(lambda: Decimal("0"))
    campaign_days = defaultdict(set)
    observed_keys = set()
    row_counts = defaultdict(int)

    with INPUT.open(encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        required = {"date", "campaign_id", "spend"}
        if not required.issubset(reader.fieldnames or []):
            raise SystemExit("Required marketing columns missing")

        for row_number, row in enumerate(reader, start=2):
            try:
                day = date.fromisoformat(row["date"])
                month = day.strftime("%Y-%m")
                campaign = row["campaign_id"].strip()
                amount = Decimal(row["spend"])
            except (ValueError, InvalidOperation, KeyError, AttributeError) as exc:
                raise SystemExit(
                    f"Invalid record at CSV line {row_number}: {type(exc).__name__}"
                )

            if not campaign or not amount.is_finite() or amount < 0:
                raise SystemExit(f"Invalid campaign or spend at line {row_number}")

            key = (day.isoformat(), campaign)
            if key in observed_keys:
                raise SystemExit(f"Duplicate campaign-day key at line {row_number}")
            observed_keys.add(key)

            if month in MONTHS:
                totals[month] += amount
                by_campaign[(month, campaign)] += amount
                campaign_days[month].add(day.isoformat())
                row_counts[month] += 1

    before, after = (totals[m] for m in MONTHS)
    if before <= 0 or after <= 0:
        raise SystemExit("Insufficient positive spend in evaluation periods")

    campaigns = sorted({
        campaign
        for month, campaign in by_campaign
    })

    changes = []
    for campaign in campaigns:
        a = by_campaign[(MONTHS[0], campaign)]
        b = by_campaign[(MONTHS[1], campaign)]
        changes.append({
            "campaign_id": campaign,
            "feb_spend": str(a),
            "mar_spend": str(b),
            "change": str(b - a),
        })

    changes.sort(
        key=lambda item: Decimal(item["change"]),
        reverse=True,
    )

    delta = after - before

    report = {
        "contract": "OPSLENS_MARKETING_DESCRIPTIVE_PROFILE_V1",
        "status": "DESCRIPTIVE_EVIDENCE_ONLY",
        "source": "data/synthetic/marketing_spend_daily.csv",
        "periods": {
            month: {
                "spend": str(totals[month]),
                "campaign_day_rows": row_counts[month],
                "distinct_observed_dates": len(campaign_days[month]),
            }
            for month in MONTHS
        },
        "total_spend_change": str(delta),
        "total_spend_change_pct": str(
            (delta / before * 100).quantize(Decimal("0.01"))
        ),
        "campaigns_observed_in_periods": len(campaigns),
        "campaign_changes": changes,
        "checks": {
            "campaign_day_keys_unique": True,
            "positive_spend_in_both_periods": True,
            "complete_calendar_coverage_verified": False,
            "independent_financial_source_verified": False,
            "campaign_incrementality_verified": False,
            "operational_mechanism_verified": False,
        },
        "limitations": [
            "Synthetic campaign data",
            "Campaign-day rows are not a complete-calendar coverage certificate",
            "Matching financial totals may share the same generating source",
            "Spend changes do not prove incremental revenue or profit",
            "Campaign-level financial attribution has not been verified",
        ],
    }

    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(
        json.dumps(report, indent=2) + "\n",
        encoding="utf-8",
    )

    print(json.dumps({
        "status": report["status"],
        "periods": report["periods"],
        "total_spend_change": report["total_spend_change"],
        "total_spend_change_pct": report["total_spend_change_pct"],
        "top_five_campaign_changes": changes[:5],
        "report_file": str(OUTPUT.relative_to(ROOT)),
    }, indent=2))


if __name__ == "__main__":
    main()
