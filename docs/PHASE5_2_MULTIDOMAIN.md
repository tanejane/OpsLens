# Phase 5.2A — Governed Cross-Domain Descriptive Investigation

## Scope

This is the **first verified two-domain capability**, not a claim of general autonomous multi-domain investigation.

- Compares *late delivery rate*, *average review score* and *low-rating rate* across **two explicitly specified, chronologically ordered purchase months**.
- Reuses existing `agent.phase4c15_delivery.measure` and `agent.phase4c11_satisfaction.measure`, which compile their own SQL and validate source row grain, rates, evidence, and provenance.
- Performs six reads (three metrics × two months), through your existing governed read-only MCP reader.
- Requires matching `eligible_orders` across delivery and review source populations for each month; matching counts **do not establish identical ID sets**, and no join is claimed.
- Returns a directional-pattern description only, **never** proof that delays caused reviews to change.
- Doesn't grant privileges, create views, modify metrics or intercept the unified chatbot automatically.
- Omits finance and product cross-domain synthesis for now. These require additional metric-to-population and attribution policies.

## Installation

Merge `agent/`, `scripts/`, `docs/` into the existing OpsLens project root; no existing file should be overwritten.

## Offline

```powershell
python -m scripts.phase5_2_validate
```

Expected `Checks passed: 30/30`. These are mocked contract tests and **not live MCP validation**.

## Live MCP test

```powershell
python -m scripts.phase5_2_live "Compare late delivery rate and review scores from May 2018 to June 2018"
```

Successful run returns `CROSS_DOMAIN_DESCRIPTIVE_COMPARISON`, the three before/after values, denominators, and evidence limitations. Live output is not predetermined by the tests.

The following intentionally requires an explicit answer instead of an unsupported causal claim:

```powershell
python -m scripts.phase5_2_live "Why did late deliveries cause poor reviews from May 2018 to June 2018?"
```

It should return `MULTIDOMAIN_NOT_VALIDATED` with `CAUSAL_OR_UNSUPPORTED_INTENT` and exit 1, **without querying MCP**.

## Next gates

1. Independently audit that the order populations on both views contain matching **order IDs** for each tested period; do not infer identical cohorts from equal counts.
2. Verify the live MCP result, including source population and numerical values, against the already governed single-domain measurements.
3. Only then expose bounded compound delivery/review questions through a distinct explicit route in `phase5_1_unified.py`; preserve existing finance/delivery/review follow-ups and fail-closed requests.
4. Add a separate governed finance integration, with financial-order eligibility denominators documented; never join aggregates as if they were one per-order financial population.
5. Add formal incident evaluations and traces before claiming general multi-domain root-cause investigation.
