# Phase 4C.18 — Product & category evidence audit

This is a **read-only gating audit**, not an authorized product/stockout executor. Source names and columns were grounded in the previous live Phase 4B.4.2 relationship audit:
- `commerce.orders` (`order_id`, `order_purchase_timestamp`)
- `commerce.order_items` (`order_id`, `order_item_id`, `product_id`, `price`, `freight_value`)
- `catalog.products` (`product_id`, `product_category_name`)

The audit checks each source grain, item→order and item→product referential completeness, join fanout, missing categories, negative/null price/freight, and purchase-time population. Product categories are **descriptive labels**; an unknown category must not silently disappear from denominators.

## Install
Merge `scripts/`, `sql/`, `docs/` into the OpsLens repository.

```powershell
python -m scripts.phase4c18_validate
$dbUser = (docker exec opslens-postgres printenv POSTGRES_USER).Trim()
Get-Content .\sql\phase4c18_product_audit.sql -Raw |
    docker exec -i opslens-postgres psql -X -q -t -A -U $dbUser -d opslens -v ON_ERROR_STOP=1 |
    Set-Content .\phase4c18_product_audit.json -Encoding utf8
if ($LASTEXITCODE -ne 0) { throw 'Product audit SQL failed' }
python -m scripts.phase4c18_assess .\phase4c18_product_audit.json
```

Expected success status (only if live checks pass): `PRODUCT_RELATIONSHIP_AUDIT_PASSED`. Any failure must be repaired before registering category metrics.

## Definitions for upcoming metric phase
- **Units sold**: count of order-item rows, *only after verifying* whether `order_item_id` represents one unit in this dataset; no generic quantity column was observed.
- **Unique orders by category**: `COUNT(DISTINCT order_id)` within each category; category counts can sum to more than all orders when orders contain multiple categories.
- **Item GMV**: sum of `commerce.order_items.price` (gross item price, not effective revenue or contribution profit); freight is separate.
- **Average item price**: `SUM(price)/COUNT(item rows with valid price)`, not per-order basket average.
- **Sales mix**: specify item GMV share or unit share, and denominator; unknown categories remain in overall totals.
- **Inventory/stockouts**: unsupported without separately validated inventory/availability evidence. No stockout inference from zero or declining sales.

The source purchase timestamp is cast to timestamp after the existing audit established source coverage; if the schema changes, review the conversion contract again. Product-level costs and category contribution profits are NOT approved. No database objects, privileges or MCP policies are modified.
