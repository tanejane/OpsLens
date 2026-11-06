# Phase 4C.25 — Guided clarification (opt-in)

## Scope
Additive `ClarificationSession` wraps existing `LanguageSession` and downstream validated dispatch. Does not modify any existing metric, SQL contract, MCP policy, database grants or category approvals. It handles only narrow, ambiguous `sales` questions and explicit reply choices.

## Install
Merge this ZIP's `agent/`, `scripts/`, `docs/` directories into the OpsLens repository. Keep the Phase 4C.24B normalization fix installed.

## Commands
```powershell
python -m scripts.phase4c25_validate
python -m scripts.phase4c24b_validate
python -m scripts.phase4c24_validate
python -m scripts.phase4c25_unified_playground
```

## Live scenario A — item GMV
Enter one line per turn:
1. `How were sales in June 2018?` => `NEEDS_CLARIFICATION`, retaining June 2018.
2. `item GMV` => `NEEDS_CLARIFICATION`, requesting approved category.
3. `health and beauty` => delegates a canonical full question to existing product NLP. Expect `item_gmv` of `107908.82` from previously reconciled, unchanged dataset; validate against real output.

## Live scenario B — units
1. `Show me sales for June 2018`
2. `units`
3. `beleza_saude` => delegates `How many health and beauty products were sold in June 2018?`. Previously reconciled value: 885 units.

## Live scenario C — financial revenue
1. `How were sales in June 2018?`
2. `financial revenue` => delegates a bounded revenue question to the prior finance router. Finance outcome needs local live validation; do not assume the router accepts the question.

## Safety, control and limitations
* Unsupported `shoe products`, unknown categories and malformed punctuation do not execute while a clarification is pending.
* `cancel` resets pending state.
* Clearly different-domain requests (e.g. delivery) clear pending state and delegate to the pre-existing router.
* This is **not** generic NLU or a universal slot filler: only configured English sales intent and the already approved `beleza_saude` aliases work. If period is omitted, guided follow-up coverage is limited and may require a complete question. No broad relative-time expression interpretation or automatic financial/product metric equivalence.
* No blanket claim that an upstream delegated result is correct; check actual source, metric and status after execution.
