# Phase 5.1B — Bounded routing repair

## Why
Live Gemini mode revealed a routing disagreement on `eh how was sales in june ah?` and an interpreter rejection on the explicit comparison `from February to March 2018`.

## Changes
* A bounded, pure `preflight` identifies **ambiguous broad sales** before making a Gemini call. A complete year/month is delegated unchanged to the existing clarification/recovery session; an incomplete year returns a **non-executable** question asking for both the metric and year. This incomplete-year response does **not yet retain a pending clarification turn**; a complete next question is required.
* Explicit revenue/profit investigations with `from [full month] to [full month] 20YY` (or `between ... and ... 20YY`) are delegated unchanged to the **existing guarded investigation router**. This does not assert that the business premise is true. The existing investigation may still clarify, reject or fail a measurement.
* Product, delivery, review, exact metric, MCP, and database permissions are unchanged.
* No automatic retry of Gemini's rejected proposals; no new permissions or generated SQL.

## Installation
Merge `agent/phase5_1_unified.py` into existing repository and add the new test script.

## Checks
```
python -m scripts.phase5_1b_validate
python -m scripts.phase5_1_validate
python -m scripts.phase4c27a_validate
python -m scripts.phase4c26_validate
```

## Live test
```
python -m scripts.phase5_1_playground --gemini
```
Try:
1. `eh how was sales in june ah?` — clarification of year and metric, no execution.
2. `How were sales in June 2018?` — existing metric clarification.
3. `Why did revenue increase while profit decreased from February to March 2018?` — goes to existing guarded investigation, where premise still must be checked.
4. `eh how much beuty item GMV in Jun 2018 ah?` — existing governed product route.
5. `what was the late delivry rate in june 2018?` — existing governed delivery route.

This patch prevents the observed router mismatch and interpreter rejection by avoiding unnecessary interpreter calls for these **specific patterns**; it does not establish broad general-language robustness. It has offline tests but requires live testing in the user's environment.
