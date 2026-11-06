# Phase 5.2B — Exact Cross-Domain Order-ID Cohort Reconciliation

## Purpose and scope

Phase 5.2A successfully compared delivery lateness and satisfaction review metrics for May/June 2018 but only verified **equal aggregate order counts**. This package independently audits whether the **same order IDs** exist in the two evidence views and in the commerce orders source, month by month. It also checks purchase timestamps, duplicate IDs and null IDs. It does **not** measure delivery–review correlations at order level, establish causality, grant MCP permission, or alter the database.

Sources:
- `commerce.orders` (source truth for purchase-time cohort; `order_purchase_timestamp`)
- `semantic.order_delivery_evidence_v1` (`order_purchase_time`)
- `semantic.order_review_evidence_v1` (`purchase_time`)

For each of May and June 2018 the SQL compares sets through **two-sided `EXCEPT`** and verifies source membership separately. It checks full timestamps for matching order IDs, and global duplicates/nulls, so equal counts alone are insufficient. Historical incident adjustments may affect delivery and review outcomes; this audit checks identity/purchase cohort only.

## Install and run (Windows PowerShell)

Merge this ZIP's `sql/`, `scripts/`, and `docs/` directories into your local OpsLens project. No files are overwritten.

```powershell
python -m scripts.phase5_2b_validate
$dbUser = (docker exec opslens-postgres printenv POSTGRES_USER).Trim()
Get-Content .\sql\phase5_2b_order_cohort_audit.sql -Raw |
    docker exec -i opslens-postgres psql -X -q -t -A -U $dbUser -d opslens -v ON_ERROR_STOP=1 |
    Set-Content .\phase5_2b_cohort_audit.json -Encoding utf8
if ($LASTEXITCODE -ne 0) { throw 'Cohort audit SQL failed; do not assess a stale output file' }
python -m scripts.phase5_2b_assess .\phase5_2b_cohort_audit.json
```

Expected status **if** live data satisfy all criteria: `EXACT_ORDER_COHORT_RECONCILED` (not pre-certified). Assessment exits nonzero on mismatch. May and June source counts were previously reported as 6873 and 6167; live assessment derives them anew and does not hard-code counts.

## What success authorizes—and what it does not

Success supports the statement that **the two order-grain evidence sources have identical purchase-month order-ID sets** for May and June 2018, matching `commerce.orders`; it does not mean the eligible delivery/review denominators are equal (different metrics exclude null outcomes differently). It does not establish that delayed orders have poor reviews or that delays cause reviews. That requires separately governed order-level joint-analysis metrics, confounder adjustment, and an explicit authorization review.

This independent SQL is **admin-side read-only audit**, NOT a query to run via restricted MCP. It creates no database views or grants and does not modify any existing business executor. Next: test finance/domain eligibility contracts, then integrate a bounded multi-domain route, without granting unsupported cross-domain joins.
