# OpsLens Phase 5.3E — pre-UI final polish and acceptance gate

## What was actually repaired

The Phase 5.3B scorer incorrectly treated the already approved `route: investigation` used by INC_001 as a route mismatch. It also ignored period metadata in Phase 5.3D's executed `observations` and `source_evidence` arrays; these omissions made the tool executions appear to have unverified periods. The changes only affect the benchmark's **interpretation of observed output**, not what the agent is permitted to execute. No new tool permissions, SQL or causal assertion paths were added.

- `scripts/phase5_3b_incident_eval.py`: verifies executed finance and measured observation periods, rejects conflicting/missing evidence intervals, recognizes the vetted finance execution route and measured planner route. A planner *without execution* never proves a period or mechanism.
- `scripts/phase5_3e_validate.py`: adversarial regression tests for accurate period handling, routing, fail-closed evidence gaps, and gate-score spoofing.
- `scripts/phase5_3e_final_gate.py`: reads genuine saved live reports from the existing core and incident evaluations. Distinguishes readiness to build a **scoped demonstration interface** from production capability or independently proved incident mechanisms.

## Apply

Merge the ZIP's `scripts/` and `docs/` into the existing repo. Back up `scripts/phase5_3b_incident_eval.py` before replacing. This update requires the Phase 5.3D agent repair installed already. There is **no** database migration or additional model/SQL permission.

## Offline regression

From the project root in PowerShell:

```powershell
python -m scripts.phase5_3e_validate
python -m scripts.phase5_3d_validate
python -m scripts.phase5_3c_validate
python -m scripts.phase5_2e_validate
python -m scripts.phase5_3b_incident_eval validate --output .\reports\phase5_3e_contracts.json
python -m scripts.phase5_3_eval offline --output .\reports\phase5_3e_core_offline.json
```

Offline checks validate code, **not live Gemini or database behavior**. Phase 5.1B's original standalone validation file targets an obsolete `preflight` API overwritten by later releases, and is not an acceptance test for the Phase 5.3D runtime. The current Phase 5.1 and 5.3D suites target the current behavior.

## Zero-cost replay before new live calls

Replay the previous observed responses with the repaired benchmark to separate old scoring mistakes from genuine missing capabilities:

```powershell
python -m scripts.phase5_3b_incident_eval score `
  --responses .\reports\phase5_3c_live_responses.json `
  --output .\reports\phase5_3e_replay_before.json
```

**Replay is not a live test.** Also note that the saved Phase 5.3C responses precede the Phase 5.3D delivery/review fixes.

## Run the actual final live evaluation

First, the seven stable regression cases:

```powershell
python -m scripts.phase5_3_eval live `
  --gemini `
  --cohort-audit .\phase5_2d_cohort_audit.json `
  --output .\reports\phase5_3e_core_live.json `
  --timeout 480
```

Then, all twelve incident probes:

```powershell
python -m scripts.phase5_3b_incident_eval live `
  --gemini `
  --timeout-per-case 240 `
  --output .\reports\phase5_3e_incidents_live.json
```

Both live commands may incur API costs. They will create `phase5_3e_core_live.json`, `phase5_3e_incidents_live.json`, and `phase5_3e_incidents_live_responses.json` (plus your existing audit file). The raw captured response file is important: do not replace it with benchmark truth.

Finally, evaluate the pre-UI scoped handoff:

```powershell
python -m scripts.phase5_3e_final_gate `
  --core-report .\reports\phase5_3e_core_live.json `
  --incident-report .\reports\phase5_3e_incidents_live.json `
  --output .\reports\phase5_3e_ui_gate.json
```

### How to interpret the gate

`SCOPED_UI_HANDOFF_READY` means: 7/7 selected core live cases passed, all 12 incident probes returned structured results, all 12 structured safety checks passed, at least three incident probes produced governed measured evidence, and zero cases ended in an unexplained block/invalid response. This is permission to proceed to **design and test a scoped UI demo**, not to claim all incident classes solved or the system production-ready.

`PRE_UI_GATE_NOT_PASSED` identifies specific blocking conditions. The script exits nonzero on failure, so use it as a CI-style gate. It will not mark offline or replay scores as live scores.

`investigations_verified` remains **separate** from descriptive coverage. By design the original benchmark needs independent reviewer attestation tied to the exact response, record provenance and mechanism-specific evidence; no self-reported model confidence can replace this.

A deliberate `ACTIONABLE_EVIDENCE_GAP` can be a **correct and safe** response, but it cannot be shown as a solved incident. The UI must display evidence gaps, unsupported domains and approval boundaries clearly. Actual source authenticity and tool-write authorization need external logs/review; the evaluator cannot prove those from model outputs alone.

## Known pre-UI limitations (do not hide)

- Regional capacity and lost-order attribution, item-level profitability mix, seller and carrier linkages, inventory-stockout counterfactual, document source precedence, and confounding stratification are **not** independently validated end-to-end by this package.
- The selected live regression set is fixed and small. After UI integration, add adversarial paraphrases, model variance/repeated trials, latency/cost budgets, cancellation and degraded-mode tests.
- A response can declare `source: semantic.*`; the scorer checks that declared source is present, **not** that a cryptographic or independently authenticated provenance chain exists.
- Neither this package nor the existing 12-probe runtime is an exhaustive retrieved-document prompt-injection test or a real write-approval audit.
- Phase 5.3D's measured single-month delivery/review evidence can support a descriptive finding, but not concentration by seller or a financial mechanism.

## Recommended scope for the interface

Expose: governed KPIs, comparisons, bounded finance investigations, validated finance+delivery+reviews descriptive analysis, evidence timestamps, verified audit artifacts, structured evidence-gap messages, and human approval requirements. Keep unsupported causal/mechanism or inventory assertions visibly unavailable until independently verified.
