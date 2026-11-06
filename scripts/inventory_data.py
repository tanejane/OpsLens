from pathlib import Path
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
RAW_DIR = ROOT / "data" / "raw"


def inspect_csv(path: Path):
    df = pd.read_csv(path)

    return {
        "file": path.name,
        "rows": len(df),
        "columns": len(df.columns),
        "column_names": list(df.columns),
        "missing_pct": {
            col: round(df[col].isna().mean() * 100, 2)
            for col in df.columns
        },
        "duplicates": int(df.duplicated().sum()),
    }


def inspect_excel(path: Path):
    book = pd.ExcelFile(path)

    results = []

    for sheet in book.sheet_names:
        df = pd.read_excel(path, sheet_name=sheet)

        results.append(
            {
                "file": path.name,
                "sheet": sheet,
                "rows": len(df),
                "columns": len(df.columns),
                "column_names": list(df.columns),
                "missing_pct": {
                    col: round(df[col].isna().mean() * 100, 2)
                    for col in df.columns
                },
                "duplicates": int(df.duplicated().sum()),
            }
        )

    return results


def main():
    results = []

    for path in RAW_DIR.rglob("*"):
        if path.suffix.lower() == ".csv":
            results.append(inspect_csv(path))

        elif path.suffix.lower() in [".xlsx", ".xls"]:
            excel_results = inspect_excel(path)
            results.extend(excel_results)

    for item in results:
        print("=" * 80)

        print(f"FILE: {item['file']}")

        if "sheet" in item:
            print(f"SHEET: {item['sheet']}")

        print(f"ROWS: {item['rows']:,}")
        print(f"COLUMNS: {item['columns']}")
        print(f"DUPLICATES: {item['duplicates']:,}")

        print("\nCOLUMN NAMES:")
        for col in item["column_names"]:
            print(f"  - {col}")

        print("\nMISSING VALUES:")
        for col, pct in item["missing_pct"].items():
            if pct > 0:
                print(f"  - {col}: {pct}%")


if __name__ == "__main__":
    main()