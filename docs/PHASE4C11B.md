# Phase 4C.11B — Live MCP satisfaction reconciliation

Additive package: only `scripts/`, `sql/`, `docs/`. Depends on 4C.11 `agent.phase4c11_satisfaction`, existing `mcp_query`, and audited `semantic.order_review_evidence_v1`.

## 1. Offline
`python -m scripts.phase4c11b_validate` — 11 checks.

## 2. Live MCP (does not grant or alter any permissions)
Run in PowerShell from the project root:

```powershell
python -m scripts.phase4c11b_live_mcp 2018-06-01 2018-07-01 | Set-Content .\phase4c11b_mcp.json -Encoding utf8
if ($LASTEXITCODE -ne 0) { Get-Content .\phase4c11b_mcp.json; throw 'MCP not validated — inspect allowlist/permissions' }
Get-Content .\phase4c11b_mcp.json
```

**Important**: A successful DB `has_table_privilege` does NOT prove MCP allowlist permits this SQL; an MCP rejection is a valid security gate. Do not modify the allowlist or apply grants automatically to force the test to pass. Escalate the exact rejected source/query to your governance approval process.

## 3. Independent PostgreSQL comparison
Fixed June 2018 purchase cohort (unrelated to MCP execution, read-only SQL):

```powershell
$dbUser=(docker exec opslens-postgres printenv POSTGRES_USER).Trim()
Get-Content .\sql\phase4c11b_independent_reconciliation.sql -Raw |
  docker exec -i opslens-postgres psql -X -q -t -A -U $dbUser -d opslens -v ON_ERROR_STOP=1 |
  Set-Content .\phase4c11b_pg.json -Encoding utf8
if ($LASTEXITCODE -ne 0) { throw 'Independent audit SQL failed' }
python -m scripts.phase4c11b_compare .\phase4c11b_mcp.json .\phase4c11b_pg.json
```

Expected successful status: `MCP_POSTGRES_RECONCILED`. Keep source attribution as **purchase time**, incident-adjusted scores as **modeled**, and output **noncausal**. The independent SQL uses the same audited review view and verifies execution and totals, not independent raw-source correctness. Do not claim deployed Gemini/NLP integration from this smoke test.
