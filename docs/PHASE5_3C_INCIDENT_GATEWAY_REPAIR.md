# OpsLens Phase 5.3C — Failure-aware incident routing repair

## Why this is needed

The real Phase 5.3B run returned `0/12` fully verified incidents, with 9 `InterpretationRejected` responses, 1 unverified comparison-period clarification, 1 multi-domain input rejection, and 1 unsupported inventory diagnosis. Safety checks passed 12/12, but **none** of those blocked responses was a completed investigation. It would be incorrect to relabel them as verified.

The fix does **not** loosen the Gemini contract, expose ground truth, or grant any new SQL permissions. It keeps the existing governed metric routes. When a response is already executable, it is returned **unchanged**. When the response is blocked, a narrowly scoped gateway can:

1. Detect a **two-explicit-month** revenue-up/profit-down question and retry through the **existing** approved finance investigator, validating its route, date boundaries and `causal_claim=false`. It does not change numerical output.
2. For a larger incident requiring unavailable evidence, return an `ACTIONABLE_EVIDENCE_GAP` plan with requested dates/domains, concrete missing evidence, and an empty `source_evidence` array. The plan is explicitly **not executable or verified**.
3. Preserve truly unsafe inputs, missing-year clarifications and unsupported questions without guessing dates or authorizing tools.
4. Fix a three-domain router scope bug: a semicolon in an unrelated one-/two-domain question no longer triggers the three-domain unsafe-input rejection. **Actual three-domain** unsafe inputs remain blocked.

The gateway uses deterministic broad evidence categories, not incident-specific IDs, fixture truth, or mechanism answers. It does not pull records, infer stockouts, assert causality, or create source citations.

## Installation

Unzip into `C:\Users\ejane\Downloads\opslens_cleaned\opslens`, merging `agent/`, `scripts/`, and `docs/`, and replacing the two existing files listed below. Preserve your local `.env`, database and existing data.

**Modified**:
- `agent/phase5_2e_multidomain_router.py` (one scope fix)
- `scripts/phase5_1_playground.py` (one post-dispatch bounded fallback)

**New**:
- `agent/phase5_3c_incident_gateway.py`
- `scripts/phase5_3c_validate.py`
- `docs/PHASE5_3C_INCIDENT_GATEWAY_REPAIR.md`

No migrations, new dependencies or MCP authorization changes.

## Offline verification (no API calls)

```powershell
python -m scripts.phase5_3c_validate
python -m scripts.phase5_2e_validate
python -m scripts.phase5_3b_incident_eval validate --output .\reports\phase5_3b_contracts_after53c.json
python -m scripts.phase5_3_eval offline --output .\reports\phase5_3_offline_after53c.json
```

The packager observed 46/46 Phase 5.3C, 37/37 Phase 5.2E, and 113/113 Phase 5.3B **offline** tests in a reconstructed source fixture. Your project contains further dependencies: you should run its full local regression tests too.

## Optional live pilot

```powershell
python -m scripts.phase5_3b_incident_eval live `
    --gemini `
    --ids INC_001 INC_006 INC_007 INC_011 `
    --timeout-per-case 240 `
    --output .\reports\phase5_3c_pilot.json
```

Then the complete unchanged benchmark:

```powershell
python -m scripts.phase5_3b_incident_eval live `
    --gemini `
    --timeout-per-case 240 `
    --output .\reports\phase5_3c_live.json
```

**What to look for:** `INC_001` may now execute the existing finance workflow; broad cases should show `ACTIONABLE_EVIDENCE_GAP` and concrete missing records rather than a generic `InterpretationRejected`. `INC_011` must not execute or approve writes. The number of **verified mechanisms may remain 0/12**: the original benchmark correctly requires independent source provenance and a reviewed attestation. A useful evidence plan is *not* a solved incident. Analyze route/status and failure codes, not just that single numerator.

The original Phase 5.3B probes and scoring rules are deliberately unchanged; ground truth is never provided to the gateway.

## Current limitations and future work

- The repaired gateway is deterministic and conservative; it is **not** a full autonomous graph-based planner or evidence retrieval layer.
- `ACTIONABLE_EVIDENCE_GAP` does not count as incident resolution; evidence sources must be obtained, linked, independently validated and authorized before a mechanism is tested.
- Model interpretation exceptions are currently surfaced as a generic `InterpretationRejected` in the old route. This patch provides a safe fallback but **does not diagnose Gemini's raw internal rejection reason**. Adding safe, structured interpreter diagnostics is a separate task.
- The 12-incident benchmark cannot be made to pass by manufacturing `verified=true`; its external source-review gate must stay in place.
- Real prompt-injection defense in retrieval still needs actual untrusted-document injection/retrieval tests and tool authorization logs. No such testing is claimed here.
