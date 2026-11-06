# Phase 4C.19 — Product and Category Metrics (validation gate)

## Current scope
One row per `(order_id,order_item_id)` at `semantic.order_item_product_evidence_v1`. All order-item rows are counted as **one item unit each**, not independent inventory records. Categories with no catalog category become the **Unknown** bucket; join should preserve every item. Metrics require a named category slug, not arbitrary identifiers. `category_order_count` counts distinct orders within a category, **not** an additive metric across categories. `item_gmv` is sum of item prices, excludes freight and **is not** effective financial revenue or category profitability. `category_gmv_share` uses *all* item-price GMV, including Unknown, as denominator.

## Install and run
Merge `agent/`, `scripts/`, `sql/`, `docs/` into OpsLens. No changes to existing finance or CX/delivery modules.

```
python -m scripts.phase4c19_validate
```

Run SQL view creation as database admin and inspect the result. Create-only SELECT view; **no MCP GRANT**:

```powershell
$dbUser=(docker exec opslens-postgres printenv POSTGRES_USER).Trim()
Get-Content .\sql\phase4c19_item_evidence.sql -Raw | docker exec -i opslens-postgres psql -X -U $dbUser -d opslens -v ON_ERROR_STOP=1
if ($LASTEXITCODE -ne 0) { throw 'View creation failed' }
Get-Content .\sql\phase4c19_reconcile.sql -Raw | docker exec -i opslens-postgres psql -X -q -t -A -U $dbUser -d opslens -v ON_ERROR_STOP=1 | Set-Content .\phase4c19_reconcile.json -Encoding utf8
if ($LASTEXITCODE -ne 0) { throw 'Source reconciliation SQL failed' }
python -m scripts.phase4c19_assess .\phase4c19_reconcile.json
Get-Content .\sql\phase4c19_role_check.sql -Raw | docker exec -i opslens-postgres psql -X -U $dbUser -d opslens -v ON_ERROR_STOP=1
```

Expected `PRODUCT_METRIC_SOURCE_RECONCILED` **if** live data reconcile. This is **not** live MCP certification. The validator uses synthetic fixtures; it does not establish correctness of database values. Authorize MCP reader only after review of source contracts and independent checks of SQL policy. No stockout conclusions or item-level profit allocation.

### Next gate
After live source audit, verify read-role access and MCP SQL allowlist, run governed `compile_metric` queries through the MCP client, compare with independent base-table totals for a fixed period, then integrate product NLP. A future category ranking should use its own bounded, tie-aware contract; this version is for explicit category filters only.
