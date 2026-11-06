# Phase 4C.21 — Audited product category catalog (discovery gate)

This is an **additive** package. Do not overwrite 4C.20 NLP or edit MCP allowlists. Its SQL is read-only and runs through the PostgreSQL administrator for a controlled, one-time category census. A catalog census does **not** authorize new English aliases or imply approval to execute through MCP.

## Installation and use
Merge `agent/`, `scripts/`, `sql/`, `docs/` into the OpsLens repository.

```powershell
python -m scripts.phase4c21_validate
$dbUser = (docker exec opslens-postgres printenv POSTGRES_USER).Trim()
Get-Content .\sql\phase4c21_category_catalog_audit.sql -Raw |
  docker exec -i opslens-postgres psql -X -q -t -A -U $dbUser -d opslens -v ON_ERROR_STOP=1 |
  Set-Content .\phase4c21_category_catalog.json -Encoding utf8
if ($LASTEXITCODE -ne 0) { throw 'Category catalog SQL failed' }
python -m scripts.phase4c21_assess .\phase4c21_category_catalog.json
python -m scripts.phase4c21_catalog_lookup .\phase4c21_category_catalog.json 'health and beauty'
python -m scripts.phase4c21_catalog_lookup .\phase4c21_category_catalog.json 'beleza_saude'
```

Expected status *if live census reconciles*: `PRODUCT_CATEGORY_CATALOG_AUDITED`. `CATEGORY_RESOLVED` for verified alias and exact canonical category. The census may have multiple purchase months and is not a period-specific GMV verification. PostgreSQL `price` amounts and source values are not a claim of revenue or profit. Counts can include `NULL` raw category; keep it in reconciliation, but do not permit category name `NULL` in the resolver.

The report provides full distinct raw categories, per-category product counts, item units, distinct orders *within category*, item GMV, and reconciliation against original `catalog.products` and `commerce.order_items`. Category order counts MUST NOT be summed into global order count.

## Governance boundary
- Only previously verified English aliases are `health and beauty`, `health & beauty`, `health_beauty` -> `beleza_saude`.
- All other canonical source categories can be resolved **only by exact source value** after passing this census; natural-language routing remains unchanged until a separate reviewed, explicit alias mapping and live execution checks.
- Reject unknown labels, category strings containing SQL punctuation, no-evidence categories, mismatched totals, invalid money, duplicate category identifiers and wrong contracts.
- Catalog uses item-grain `commerce.order_items.price`, not `semantic.order_economics`. No inventory, stockout, or causal claims.
- Next phase: inspect audited category names; approve a versioned curated alias table; add bounded extraction with ambiguity controls to the NLP layer; live-test each newly enabled category.

No SQL table/view, grants, migrations, or allowlist changes are included.
