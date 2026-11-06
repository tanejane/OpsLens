# Phase 4C.21B — Catalog-backed category alias approval gate

This increment is **additive**. It does not overwrite the validated 4C.20 conversational router or 4C.19 metric executor and does not change SQL, grants, or MCP allowlists.

## Why this phase exists

The 4C.21 catalog is audited (74 category rows, 73 with items), but new English translations are **not** certified. The approved `health and beauty` aliases remain valid; other names must be explicitly reviewed. The local category census JSON contains the full canonical set; a review sheet must be generated from *that* file rather than filling in guessed translations.

## Setup and commands (PowerShell, repo root)

Merge `agent/`, `scripts/`, `docs/` from this ZIP into OpsLens. Preserve the existing package files.

```powershell
python -m scripts.phase4c21b_validate
python -m scripts.phase4c21b_review template .\phase4c21_category_catalog.json .\phase4c21b_alias_review.csv
```

Open the generated CSV. Every source category with item evidence has a row. For names you want to allow, enter a checked `english_alias` (e.g. `furniture` only if you personally verify the correct canonical source category), change `approved` to `yes`, fill in a reviewer and meaningful review note. Leave unknown translations blank and `approved=no`. Multiple aliases for one category may be added as extra rows, provided every alias is globally unique. Preserve the five CSV headers exactly. This is a **human review process**, not machine-generated approval. A spreadsheet editor may reformat CSV; check exported UTF-8 and all columns.

```powershell
python -m scripts.phase4c21b_review validate .\phase4c21_category_catalog.json .\phase4c21b_alias_review.csv
python -m scripts.phase4c21b_review resolve .\phase4c21_category_catalog.json .\phase4c21b_alias_review.csv 'health and beauty'
# Once you have manually approved a particular alias, test it:
python -m scripts.phase4c21b_review resolve .\phase4c21_category_catalog.json .\phase4c21b_alias_review.csv 'YOUR APPROVED ALIAS'
```

Expected statuses: `ALIAS_REVIEW_TEMPLATE_CREATED`, `REVIEWED_ALIASES_VALIDATED`, and `CATEGORY_RESOLVED`. Rejected inputs exit nonzero and report `CATEGORY_ALIAS_REVIEW_FAILED`. The `new_english_aliases` result lists *only* new approved aliases, not all 73 categories. A valid empty review file is allowed and approves zero new aliases.

## Safety and scope

- The catalog itself must pass the 4C.21 source audit. Aliases can target only actual canonical categories with item evidence.
- Exact canonical names and the three previously verified health/beauty aliases are reserved. Any attempt to redirect an existing identifier fails closed.
- Reviewed aliases are normalized for case and whitespace only; this phase **does not** perform fuzzy matching, autocorrection, multilingual translation, or infer intent.
- All newly approved names remain **outside the current 4C.20 natural-language router** until a separate integration test and live verification. This is intentional: no broad routing changes without validated mappings.
- This document is a review workflow, not a claim that a named reviewer approved a translation. Each CSV edit is local; no cryptographic signatures or independent organizational approval exist.
- `approved_for_mcp=false`: the alias review does not authorize any new data sources or SQL.
- Item GMV is not governed financial revenue. Inventory/stockout, causal, margin, and product-profit claims remain unsupported.

## Next step

After local review succeeds, integrate only the approved mapping into the bounded product NLP router and run live MCP checks with two new categories, then add typo tolerance and multilingual intent parsing with ambiguity thresholds and safe clarification. Do not turn free-form typo correction directly into SQL or category identifiers.
