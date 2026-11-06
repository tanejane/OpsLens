# Phase 4C.15 — Governed Delivery Metric Executor

**Additive.** Merge `agent/`, `scripts/`, `sql/`, `docs/`. Requires previously audited `semantic.order_delivery_evidence_v1` (Phase 4C.14). No grants, schema migrations, or NLP routing changes.

## Metric contracts

- `late_delivery_rate`: percent of lateness-eligible orders with effective actual delivery time later than promised time; excludes missing dates.
- `average_delivery_days`: mean days between purchase and effective actual delivery for duration-eligible orders.
- `delivered_order_count`: count of duration-eligible orders (purchase and delivery valid with nonnegative duration), **not** necessarily all orders with non-null actual delivery timestamps.
- `delivery_evidence_coverage`: percentage of purchase-cohort orders with actual and promised timestamps.

Each query is purchase-time scoped, read-only, one aggregate row from an order-grain view. Lateness and duration populations can differ. All metrics are descriptive; timestamps may be modeled/adjusted.

## Verification

```powershell
python -m scripts.phase4c15_validate
$dbUser=(docker exec opslens-postgres printenv POSTGRES_USER).Trim()
Get-Content .\sql\phase4c15_role_check.sql -Raw | docker exec -i opslens-postgres psql -X -U $dbUser -d opslens -v ON_ERROR_STOP=1
```

Do not grant automatically if the MCP reader lacks access: review the source SQL policy and your explicit authorization workflow first.

```powershell
python -m scripts.phase4c15_live_mcp 2018-06-01 2018-07-01 > .\phase4c15_mcp.json
if ($LASTEXITCODE -ne 0) { Get-Content .\phase4c15_mcp.json; throw 'MCP verification failed' }
Get-Content .\sql\phase4c15_independent_june.sql -Raw | docker exec -i opslens-postgres psql -X -q -t -A -U $dbUser -d opslens -v ON_ERROR_STOP=1 > .\phase4c15_pg.json
if ($LASTEXITCODE -ne 0) { throw 'Postgres reference failed' }
python -m scripts.phase4c15_compare .\phase4c15_mcp.json .\phase4c15_pg.json
```

Expected statuses only if live environment permits and reconciles: `LIVE_MCP_VALIDATED`, `MCP_POSTGRES_RECONCILED`. PostgreSQL independent reference fixed to June 2018; for other months write a separate audited reference rather than comparing against June.

## Next gate

Once live metric and reference validations pass, integrate four metric IDs into the unified natural-language dispatcher with explicit period and metric grounding. Delivery-to-review joins are **not yet approved**.
