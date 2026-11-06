# OpsLens Phase 4C.13 — Governed Customer Satisfaction Comparisons

## Scope
Additive integration. Requires existing Phase 4C.10 review view, Phase 4C.11 governed metric executor, Phase 4C.12 customer-satisfaction NLP, Phase 4C.8 unified dispatch and all preceding dependencies. Does not alter DB schema, roles, allowlists, or financial executor.

## What it does
- Comparison requests such as `Did satisfaction drop from May to June 2018?` execute **two independently governed** monthly metrics and return a signed delta and direction.
- Accepts `May to June 2018` or `May 2018 versus June 2018` and carries the active CX metric for follow-ups such as `Compare May and June 2018` after selecting `low_rating_rate`.
- No implicit baseline; exact two periods required. Refuses ambiguous customer vs order counts, unsupported investigation, multiple months, reverse periods and malformed dates.
- Fails closed on MCP error and on metric-source/policy/grain/unit mismatch. Preserves context on failure. A successful comparison updates the satisfaction context to the **later** month.
- Review scores are purchase-cohort averages of one order-level score per order, with modeled incident adjustments possible. Low-rating and coverage comparisons are **percentage-point differences**, not relative percent changes.

## Install
Extract and merge `agent/`, `scripts/`, `docs/` into project root.

## Validate offline
`python -m scripts.phase4c13_validate` — expected `Checks passed: 20/20`

## Test live
`python -m scripts.phase4c13_unified_playground`

Try in order:
1. `What was our average customer satisfaction score in June 2018?`
2. `Did satisfaction drop from May to June 2018?` (comparison should show an increase of ~0.05959 in score)
3. `And the bad review rate?` (single month June, since successful comparison updates context)
4. `Compare May and June 2018` (rate should decrease by ~0.91063 percentage points)
5. `How many customers left reviews in June 2018?` (clarification)
6. `What was our effective revenue in April 2018?` (prior finance route)
7. `Which five sellers received the most unique orders in June 2018?` (prior graph route)

## Not yet supported
- Multiple-month time-series trends, arbitrary date spans and causal satisfaction investigations.
- Delivery-linked analysis, cohort controls, seasonality correction or tests for statistical significance.
- This increment's 20 checks are **offline**. Real MCP and dispatcher live testing remain required.
