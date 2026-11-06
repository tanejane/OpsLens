# Phase 4C.19B — product/category live MCP evidence gate

Prerequisites: Phase 4C.19 installed, `semantic.order_item_product_evidence_v1` created and source reconciliation passed. Existing `mcp_query` from Phase 4B.57 and MCP in-process server. No permissions or migrations are changed by this package. Source dates are attributed to order purchase time.

## Offline tests

```powershell
python -m scripts.phase4c19b_validate
```

Expected: `Checks passed: 17/17`. Offline tests use invented fixture values solely to test validation; they are not measurements from the user's database.

## Live MCP — June 2018 health_beauty

Use `Set-Content -Encoding utf8` for BOTH output JSON files in Windows PowerShell 5.1, because its `>` operator may create UTF-16 files.

```powershell
python -m scripts.phase4c19b_live_mcp 2018-06-01 2018-07-01 health_beauty |
    Set-Content .\phase4c19b_mcp.json -Encoding utf8
if ($LASTEXITCODE -ne 0) {
    Get-Content .\phase4c19b_mcp.json
    throw 'Product MCP verification failed; do not bypass the allowlist'
}
Get-Content .\phase4c19b_mcp.json
```

Successful live result: `LIVE_MCP_VALIDATED`. This check alone does not establish independent agreement with raw tables.

## Independent comparison against raw tables

```powershell
$dbUser=(docker exec opslens-postgres printenv POSTGRES_USER).Trim()
Get-Content .\sql\phase4c19b_independent_june_health_beauty.sql -Raw |
    docker exec -i opslens-postgres psql -X -q -t -A -U $dbUser -d opslens -v ON_ERROR_STOP=1 |
    Set-Content .\phase4c19b_pg.json -Encoding utf8
if ($LASTEXITCODE -ne 0) { throw 'Independent product SQL failed' }
python -m scripts.phase4c19b_compare .\phase4c19b_mcp.json .\phase4c19b_pg.json
```

Expected if values reconcile: `MCP_POSTGRES_RECONCILED`, `metric_count: 5`. The independent reference SQL is fixed to June 2018 and `health_beauty` and does not reuse the semantic view. Comparison checks totals, item distinctness, category counts, GMV, derived metrics, units, and unsupported causal/inventory claims.

## Limits

- Only one audited category and month are independently reconciled by this package; wider periods remain unverified.
- Item GMV excludes freight and is not the same as audited effective revenue.
- An order containing several categories can count once in each category, so category order counts must not be summed.
- `Unknown` category must be kept in total GMV; product sales do not prove inventory stockouts.
- Live verification does not imply free-form query rights. If MCP denies the view, investigate the allowlist before changing any permission.
