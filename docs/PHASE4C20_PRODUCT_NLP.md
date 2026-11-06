# Phase 4C.20 — Governed Product NLP (bounded first slice)

## Scope
Adds a strictly deterministic English-to-canonical category mapping for the one independently verified Olist category `health and beauty` -> `beleza_saude` (also `health_beauty`, `health & beauty`, and direct canonical slug). This is deliberately not a generic translation dictionary. It delegates all source metric calculations to the unchanged `agent.phase4c19_product.measure`, using schema-qualified read-only SQL through existing MCP reader.

Supports the five 4C.19 metrics, explicitly named purchase month/year, and within-product follow-ups that replace either period or metric while preserving category. No period-comparison, ranking, stockout, availability, causal, profitability, margin, or all-category analysis. Other-domain questions are delegated to the existing 4C.17 dispatcher; product state clears when switching away.

## Installation
Merge `agent/`, `scripts/`, and `docs/` into the local OpsLens repository. Do not replace existing files; only these new filenames are included. Prerequisites: the previously verified `agent/phase4c19_product.py` with the 4C.19B CTE-policy patch, Phase 4C.17 session modules, existing MCP server and approved read access to `semantic.order_item_product_evidence_v1`.

## Tests

```powershell
python -m scripts.phase4c20_validate
python -m scripts.phase4c19_validate
python -m scripts.phase4c19_policy_regression
```

## Interactive live test

```powershell
python -m scripts.phase4c20_unified_playground
```

Enter, in order:

```
How many health and beauty products were sold in June 2018?
And the item GMV?
What percentage of item GMV was health and beauty in June 2018?
What about May 2018?
What is the late delivery rate in June 2018?
exit
```

For June 2018 `beleza_saude`, earlier verified baseline was 885 item rows and item GMV 107908.82. Every live response must be inspected; this package has offline simulation only and does not claim live integration passed. If the reader rejects, investigate MCP authorization and contract, do not weaken policy.

## Behavior and limitations
- `units_sold` counts item records; not verified inventory quantities.
- `item_gmv` excludes freight, and is not governed finance revenue or contribution profit.
- Unclassified category items remain in the total denominator.
- Historical purchase-month comparisons not part of this increment.
- A missing date/category requests clarification; an empty historical category may cause existing denominator validation to reject the calculation (fail closed).
- A deliberately small set of verified aliases is used instead of guessing a translation for unseen categories.
- The interactive integration imports the same older sources as the 4C.17 interactive playground; its compatibility with your exact repo must be live verified.
