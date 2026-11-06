# OpsLens 4C.17 — Governed delivery comparisons

Additive install: merge `agent/`, `scripts/`, `docs/` into the existing repository with Phase 4C.16 and 4C.15 installed.

No migration, role grant, or MCP allowlist change. Uses the existing `phase4c15_delivery.measure` for each specified purchase month. The only authorized queries are compiled from registered metrics and fixed date parameters. No LLM SQL, no causal inference, no delivery-review joins.

## Tests

`python -m scripts.phase4c17_validate`

`python -m scripts.phase4c17_unified_playground`

Enter in order:

1. `Did late delivery improve from May 2018 to June 2018?` — measured `late_delivery_rate`, June should be lower than May.
2. `Compare average delivery time from May to June 2018` — measured duration comparison; May about 11.42 days, June about 9.32 days.
3. `And the late delivery rate?` — June single-period rate.
4. `Compare May and June 2018` — inherits latest active delivery metric.
5. `What was our average customer satisfaction score in June 2018?` — existing CX route.
6. `What was our effective revenue in April 2018?` — existing finance route.
7. `Which five sellers received the most unique orders in June 2018?` — existing graph route.

When testing, do not paste numbered prefixes (e.g. `1.`) into the playground. Failures must not mutate successful conversation context. Comparison values reflect different purchase-month cohorts, may contain modeled delivery adjustments, and do not establish causation. This phase does not authorize delivery-to-review analysis.
