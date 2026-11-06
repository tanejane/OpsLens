# Phase 4C.24B — Single-pass normalization reliability patch

## Bug and repair
Previously `PHRASES` were executed sequentially on the already-modified string. `beuty` became `health and beauty`; a later `beauty` rule matched **inside the new replacement**, yielding `health and health and beauty`. The patch builds a single alternation regex with phrase-priority order and substitutes **once over the original preprocessed string**. Its callback chooses the first matching reviewed rule at the source span. New replacement text is never rescanned in the same pass.

Examples: `How many beuty products were sold in Jun 18?` -> `How many health and beauty products were sold in June 2018?`. Normalizing this result again gives the same sentence with no additional corrections. Exact source category IDs remain untouched. The existing Chinese lexicon is unchanged and does not constitute general multilingual support.

## Install
Copy `agent/phase4c24_language.py` **over** the existing file and add `scripts/phase4c24b_validate.py`. Other files are explanatory. No SQL, DB, MCP, roles, allowlist, or business metric changes.

```powershell
python -m scripts.phase4c24b_validate
python -m scripts.phase4c24_validate
python -m scripts.phase4c20_validate
python -m scripts.phase4c24_unified_playground
```

Interactive verification: `How many beuty products were sold in Jun 18?`, `And the item GMV?`, `What is the late delivry rate in June 2018?`, `How is sales doing?`, `Why did beauty sales decrease in June 2018?`. Verify the **interpreted_question**, not just the metric value.

## Boundaries
Typos remain explicitly enumerated, not fuzzy matched. Ambiguities, unsupported categories, inventory questions and causal requests remain subject to the same downstream guards. Offline validation cannot prove live MCP compatibility: run the playground locally and check its outputs before closing the live gate.
