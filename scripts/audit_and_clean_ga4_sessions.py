
from pathlib import Path
import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[1]
INPUT = PROJECT_ROOT / "data" / "processed" / "ga4_sessions.csv"
OUTPUT = PROJECT_ROOT / "data" / "processed" / "ga4_sessions_clean.csv"
REPORT = PROJECT_ROOT / "docs" / "ga4_audit.txt"

PROJECT_ROOT.joinpath("docs").mkdir(parents=True, exist_ok=True)

df = pd.read_csv(INPUT)

print("=" * 78)
print("OPSLENS GA4 SESSION AUDIT + CONSOLIDATION")
print("=" * 78)
print(f"Input rows: {len(df):,}")
print(f"Columns: {len(df.columns)}")

required = {
    "session_date",
    "user_pseudo_id",
    "session_id",
    "session_key",
    "page_view_count",
    "view_item_count",
    "add_to_cart_count",
    "begin_checkout_count",
    "purchase_count",
    "purchase_revenue",
}
missing = required - set(df.columns)
if missing:
    raise RuntimeError(f"Missing required columns: {sorted(missing)}")

df["session_date"] = pd.to_datetime(df["session_date"], errors="coerce")

dup_mask = df["session_key"].duplicated(keep=False)
dup_rows = df.loc[dup_mask].copy()
dup_extra = int(df["session_key"].duplicated().sum())
dup_unique_keys = int(dup_rows["session_key"].nunique())

print(f"Repeated session_key extra rows: {dup_extra:,}")
print(f"Unique repeated session_keys: {dup_unique_keys:,}")

if len(dup_rows):
    date_counts = dup_rows.groupby("session_key")["session_date"].nunique()
    same_date_repeats = int((date_counts <= 1).sum())
    cross_date_repeats = int((date_counts > 1).sum())
else:
    same_date_repeats = 0
    cross_date_repeats = 0

print(f"Repeated keys spanning multiple dates: {cross_date_repeats:,}")
print(f"Repeated keys confined to one date: {same_date_repeats:,}")

count_cols = [
    "page_view_count",
    "view_item_count",
    "add_to_cart_count",
    "begin_checkout_count",
    "purchase_count",
    "purchase_revenue",
]
for c in count_cols:
    df[c] = pd.to_numeric(df[c], errors="coerce").fillna(0)

def first_non_null(series):
    non_null = series.dropna()
    if len(non_null) == 0:
        return pd.NA
    as_str = non_null.astype(str)
    keep = ~as_str.str.strip().isin(["", "nan", "None"])
    filtered = non_null[keep]
    return filtered.iloc[0] if len(filtered) else non_null.iloc[0]

dim_cols = [
    c for c in [
        "device_category",
        "country",
        "traffic_source",
        "traffic_medium",
        "traffic_campaign",
    ]
    if c in df.columns
]

agg = {
    "session_date": "min",
    "user_pseudo_id": first_non_null,
    "session_id": first_non_null,
}
for c in dim_cols:
    agg[c] = first_non_null
for c in count_cols:
    agg[c] = "sum"

clean = df.groupby("session_key", as_index=False, dropna=False).agg(agg)

clean["did_purchase"] = (clean["purchase_count"] > 0).astype(int)
clean["did_checkout_abandon"] = (
    (clean["begin_checkout_count"] > 0)
    & (clean["purchase_count"] == 0)
).astype(int)

clean = clean.sort_values(
    ["session_date", "user_pseudo_id", "session_id"],
    kind="stable"
).reset_index(drop=True)

exact_dupes = int(clean.duplicated().sum())
session_dupes = int(clean["session_key"].duplicated().sum())
date_min = clean["session_date"].min()
date_max = clean["session_date"].max()

purchase_rate = float(clean["did_purchase"].mean())
checkout_sessions = int((clean["begin_checkout_count"] > 0).sum())
abandon_sessions = int(clean["did_checkout_abandon"].sum())
checkout_abandon_rate = (
    abandon_sessions / checkout_sessions if checkout_sessions else 0.0
)

print(f"\nCanonical session rows: {len(clean):,}")
print(f"Rows consolidated: {len(df) - len(clean):,}")
print(f"Exact duplicate rows after cleaning: {exact_dupes:,}")
print(f"Duplicate session_key after cleaning: {session_dupes:,}")
print(f"Date range: {date_min.date()} -> {date_max.date()}")
print(f"Purchase session rate: {purchase_rate:.2%}")
print(f"Checkout sessions: {checkout_sessions:,}")
print(f"Checkout-abandon sessions: {abandon_sessions:,}")
print(f"Checkout-abandon rate: {checkout_abandon_rate:.2%}")
print(f"Total purchase revenue: {clean['purchase_revenue'].sum():,.2f}")

print("\nMissingness:")
missingness = clean.isna().mean().sort_values(ascending=False)
for col, pct in missingness.items():
    if pct > 0:
        print(f"  {col}: {pct:.2%}")

if "device_category" in clean.columns:
    print("\nDevice distribution:")
    print(clean["device_category"].fillna("<NULL>").value_counts(dropna=False).head(10))

if "traffic_source" in clean.columns:
    print("\nTop traffic sources:")
    print(clean["traffic_source"].fillna("<NULL>").value_counts(dropna=False).head(10))

clean.to_csv(OUTPUT, index=False)

lines = [
    "OPSLENS GA4 AUDIT",
    "=" * 50,
    f"Input rows: {len(df):,}",
    f"Canonical session rows: {len(clean):,}",
    f"Rows consolidated: {len(df) - len(clean):,}",
    f"Repeated session keys (extra rows): {dup_extra:,}",
    f"Repeated keys spanning multiple dates: {cross_date_repeats:,}",
    f"Repeated keys confined to one date: {same_date_repeats:,}",
    f"Exact duplicate rows after cleaning: {exact_dupes:,}",
    f"Duplicate session_key after cleaning: {session_dupes:,}",
    f"Date range: {date_min.date()} -> {date_max.date()}",
    f"Purchase session rate: {purchase_rate:.2%}",
    f"Checkout sessions: {checkout_sessions:,}",
    f"Checkout-abandon sessions: {abandon_sessions:,}",
    f"Checkout-abandon rate: {checkout_abandon_rate:.2%}",
    f"Total purchase revenue: {clean['purchase_revenue'].sum():,.2f}",
]
REPORT.write_text("\n".join(lines), encoding="utf-8")

print("\nSaved canonical GA4 sessions:")
print(OUTPUT)
print("\nSaved audit report:")
print(REPORT)
