from pathlib import Path
import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parents[1]

RAW_DIR = PROJECT_ROOT / "data" / "raw" / "ga4_ecommerce"
OUTPUT_DIR = PROJECT_ROOT / "data" / "processed"
OUTPUT_PATH = OUTPUT_DIR / "ga4_sessions.csv"

OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


# Find part1.csv ... part8.csv
files = sorted(
    RAW_DIR.glob("part*.csv"),
    key=lambda p: int("".join(filter(str.isdigit, p.stem)))
)

if len(files) != 8:
    raise RuntimeError(
        f"Expected 8 GA4 CSV parts, but found {len(files)}:\n"
        + "\n".join(str(f.name) for f in files)
    )

print("Files found:")
for f in files:
    print(" -", f.name)


frames = []

for file in files:
    df = pd.read_csv(file)
    print(f"{file.name}: {len(df):,} rows")
    frames.append(df)


combined = pd.concat(frames, ignore_index=True)

print("\nCombined rows:", f"{len(combined):,}")
print("Columns:", len(combined.columns))


# Basic duplicate check
duplicate_rows = combined.duplicated().sum()
print("Exact duplicate rows:", f"{duplicate_rows:,}")


# Session key duplicate check
if "session_key" in combined.columns:
    duplicate_sessions = combined["session_key"].duplicated().sum()
    print("Duplicate session_key values:", f"{duplicate_sessions:,}")


# Expected row count from BigQuery
EXPECTED_ROWS = 360_974

if len(combined) != EXPECTED_ROWS:
    print(
        f"\nWARNING: Expected {EXPECTED_ROWS:,} rows "
        f"but found {len(combined):,}."
    )
else:
    print(f"\nPASS: Row count matches expected {EXPECTED_ROWS:,}.")


combined.to_csv(OUTPUT_PATH, index=False)

print("\nSaved merged GA4 file to:")
print(OUTPUT_PATH)