# Phase 5.2D — February/March exact order-ID reconciliation

## Purpose
Independent read-only check that `commerce.orders`, `semantic.order_delivery_evidence_v1`, and `semantic.order_review_evidence_v1` have identical order-ID sets and purchase timestamps for **February 2018** and **March 2018**. This duplicates the approved structure of 5.2B without changing its May/June contract.

## Install
Merge the `sql/` and `scripts/` files into the existing OpsLens repo. No schema migrations, role grants, or MCP allowlist changes.

## Run (PowerShell)
```powershell
python -m scripts.phase5_2d_validate
$dbUser = (docker exec opslens-postgres printenv POSTGRES_USER).Trim()
Get-Content .\sql\phase5_2d_order_cohort_audit.sql -Raw |
    docker exec -i opslens-postgres psql -X -q -t -A -U $dbUser -d opslens -v ON_ERROR_STOP=1 |
    Set-Content .\phase5_2d_cohort_audit.json -Encoding utf8
if ($LASTEXITCODE -ne 0) { throw 'February/March cohort SQL failed' }
python -m scripts.phase5_2d_assess .\phase5_2d_cohort_audit.json
if ($LASTEXITCODE -ne 0) { throw 'February/March exact cohort audit failed' }
```

## Meaning of pass
`EXACT_ORDER_COHORT_RECONCILED` confirms exact order-ID set membership in the **three audited source/views for the two specified months**. Same IDs does **not** imply each order has eligible review and delivery measurements. The financially eligible order population is different from the overall operational cohort, and **is not** included in the identity guarantee. This is not a causal test, not approval for joins, and not new MCP authorization.

## Next
After a live pass, integrate the bounded three-domain capability into the unified conversational router with independently checked intent, periods, and authorization. Do not use this audit to claim the same exact cohort for arbitrary months.
