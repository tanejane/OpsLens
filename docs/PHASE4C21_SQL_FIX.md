# Phase 4C.21 PostgreSQL census repair

The original query used `FULL JOIN ... ON s.raw_category IS NOT DISTINCT FROM i.raw_category`. PostgreSQL does not support that non-merge/hash-joinable FULL JOIN condition. The replacement combines the separately aggregated product and item populations using `UNION ALL`, and then groups once by raw category. PostgreSQL groups NULL categories into one bucket, preserving uncategorized product/item counts. Since each side provides only its own nonzero measure columns, summation does not multiply products or items. No permission changes or database writes are required.

Replace `sql/phase4c21_category_catalog_audit.sql` and optionally add `scripts/phase4c21_sql_regression.py`. Re-run offline validators, export with `ON_ERROR_STOP=1`, then audit. Do not run catalog lookup on failed/empty SQL output.
