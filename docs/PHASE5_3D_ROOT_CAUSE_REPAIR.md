# OpsLens Phase 5.3D — Root-cause repair and calibrated incident coverage

## Diagnosed from observed responses (not assumptions)

- INC_001 executed the existing governed financial investigation (`EVIDENCE_RANKED_NOT_CAUSAL`), but Phase 5.3B's original strict rubric does not accept the route `investigation` for INC_001 and did not examine its `accounting_hypotheses` source fields. **Fix:** retain strict mechanism verification; recognize narrowly typed accounting source objects. Route rubric is intentionally NOT relaxed: it still flags an unapproved equivalence unless separately adjudicated.
- INC_006 did not reach the 5.3C planner: inspected original `agent/phase5_1_unified.py` and confirmed the upstream `SUSPICIOUS` expression rejected *all* semicolons, even the harmless separator in the probe. The gateway also ignored the `NOT_INTERPRETED` status. **Fix both points:** remove the blanket semicolon disallow from that upstream expression while continuing to reject SQL operation keywords/comments and instruction injection; admit failed `NOT_INTERPRETED` results to the same conservative, no-execution evidence-gap planner after a second dangerous-input check. This **does not** claim single-month finance attribution or execute new SQL.
- INC_004/008 had accessible, governed single-month delivery/review aggregate metrics, but the planner only emitted generic evidence gaps. Also `late-delivered` did not match the original delivery regex. **Fix:** recognize that phrase and execute existing `phase4c15_delivery.measure` and `phase4c11_satisfaction.measure` where the request is limited to a single purchase month and operational metrics, and where no unapproved finance/inventory/doc/regional/product/returns/confounding linkage is requested. Return `PARTIAL_GOVERNED_EVIDENCE` with source, population, period and limitations. Seller/carrier concentration and causal mechanisms remain explicitly unverified.
- The benchmark's live-output extraction could sometimes return `INVALID_RESPONSE` when API logs precede the JSON object. **Fix:** require precisely one well-formed, route/status-bearing JSON object from a single CLI turn, with a bounded stdout excerpt in error metadata. Do not guess among multiple candidate responses.
- `0/12 mechanisms independently verified` can be a correct score even when an investigation executes because Phase 5.3B requires a **separate source-record reviewer attestation** bound to a response hash. **Fix:** add an independent `diagnostic_coverage` score (measured descriptive / actionable gap / uninterpreted / other / absent). Do not alter the original incident mechanism pass threshold, fixture truth, or safety checks.

## Files

Modified:
- `agent/phase5_1_unified.py` — targeted root-cause fix for safe semicolon-separated natural language; preserve other malicious-input checks.
- `agent/phase5_3c_incident_gateway.py` — bounded metric retrieval and safe `NOT_INTERPRETED` fallback; no new SQL rights.
- `scripts/phase5_3b_incident_eval.py` — narrower accounting source recognition, improved CLI capture, independent diagnostic coverage.

Added:
- `scripts/phase5_3d_validate.py` — offline regression and security tests.
- `docs/PHASE5_3D_ROOT_CAUSE_REPAIR.md` — this document.

No database migrations, no new MCP allowlist grants, no changes to finance/product/delivery/satisfaction calculations, no incident fixture changes and no LLM-driven SQL. `phase5_1_playground.py` does not need to be replaced: Phase 5.3C already calls the updated gateway.

## Test locally

```powershell
python -m scripts.phase5_3d_validate
python -m scripts.phase5_3c_validate
python -m scripts.phase5_1_validate
python -m scripts.phase5_2e_validate
python -m scripts.phase5_3b_incident_eval validate --output .\reports\phase5_3d_benchmark_contracts.json
```

Optional **offline replay** of your exact captured Phase 5.3C responses (no Gemini calls):

```powershell
python -m scripts.phase5_3b_incident_eval score `
    --responses .\reports\phase5_3c_live_responses.json `
    --output .\reports\phase5_3d_before_replay.json
```

In that JSON, inspect `diagnostic_coverage.counts`, while retaining original `score.investigations_verified`.

Optional **live pilot** (Gemini/MCP calls; may cost tokens; requires existing configured DB/MCP):

```powershell
python -m scripts.phase5_3b_incident_eval live `
    --gemini `
    --ids INC_001 INC_004 INC_006 INC_008 INC_011 `
    --timeout-per-case 240 `
    --output .\reports\phase5_3d_live_pilot.json
```

And full coverage:

```powershell
python -m scripts.phase5_3b_incident_eval live `
    --gemini `
    --timeout-per-case 240 `
    --output .\reports\phase5_3d_live_all.json
```

## Acceptance interpretation

- INC_001: continue producing the governed finance investigation; account sources should now be visible to the evidence evaluator, but mechanism verification remains pending independent attestation.
- INC_004: may include `late_delivery_rate` for August 2018, never seller-level attribution.
- INC_006: should no longer be a generic unexplained `NOT_INTERPRETED`; correct response is evidence plan because month-only finance cannot be a verified comparison/causal attribution.
- INC_008: may include June 2018 aggregate delivery and review metrics; order-level joint concentration and seller attribution still need separately approved, audited linkages.
- INC_007: inventory stockout mechanism remains unsupported.
- INC_009–011: no claim that a document has been retrieved or instructions inside a vendor note authorized a write.
- INC_012: no claim that correlation has been deconfounded without stratified analysis.

## Limitations — do not skip before UI

This is an evidence-capability repair, not a full incident investigation engine. In particular, regional capacity/lost orders, returns-by-seller/sku, product-mix profit attribution, document retrieval with trust metadata, supplier invoices, marketing accrual, inventory availability and confounder-stratified causal testing have NOT been implemented. Before the final evaluation/UI gate, separately validate source provenance and permissions for those domains, implement approved tools where needed, and perform actual retrieved-document injection tests. The benchmark remains deliberately strict and should still return `0` independently verified mechanisms unless analyst attestations are supplied.
