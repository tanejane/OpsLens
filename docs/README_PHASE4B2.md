# OpsLens Phase 4B.2 — governed metrics (first increment)

## What this does
Adds a metric-ID-first path: Gemini chooses a named metric and dimensions, application-owned formulas compile read-only SQL, live MCP metadata verifies required columns, MCP runs the query. **No arbitrary LLM SQL.** Old 4B.1 playground is unchanged.

## Installation
Merge `agent/`, `scripts/`, and `docs/` into the **cleaned** OpsLens source folder. Docker/PostgreSQL and Gemini must be configured as in Phase 4B.1.

```powershell
python scripts/phase4b2_validate_metrics.py
python -m agent.phase4b2_metric_playground
```

Try:
- `What was the gross margin percentage in June 2018?`
- `How many orders were placed in June 2018?`
- `Which categories had the lowest margins?` — **expected BLOCKED**, not a made-up answer (no governed category join yet)
- `How many orders did each seller receive in 2018?` — **expected BLOCKED** until seller relationship exists

## Critical scope and next steps
This is **not** the entire Phase 4B.2. It intentionally has no governed multi-relation join graph, no category margin result, no seller order ranking, no causal investigations, and no runtime evidence of correctness from your PostgreSQL yet. It cannot understand every arbitrary metric. The tests validate SQL contracts, not real business values.

There is an inconsistency in the original `config/metric_catalog.json`: `orders` is documented as COUNT(DISTINCT order_id) from `semantic.daily_commerce`, but that view has `orders` aggregates and no order_id. This package instead counts order_id in `commerce.orders`. The original `checkout_abandon_rate` catalog formula references `checkout_abandon_sessions`, absent from the inspected `semantic.ga4_funnel_daily` SQL; **the compiler blocks it** until an approved source and denominator/numerator are verified. Existing catalog remains unchanged to avoid a blind migration.

GA4 daily view does not include device/traffic dimensions; those breakdowns require a vetted lower-grain source or new aggregated view.

The semantic view `semantic.product_mix_effective` is `SELECT *` from a staging fixture, so its actual column contracts were not verifiable from the supplied migration. We must inspect `describe_relation` live before building category profit margin and approved joins. The business definition of seller order count must also be agreed (distinct orders with any seller item vs seller-order pairs).

## Safety
Read-only MCP remains the execution boundary; no raw SQL from the model; date text casting inherited from 4B.1 allowlist; no hidden truth; `NULLIF` guards zero denominators. Keep `.env` out of archives and Git.
