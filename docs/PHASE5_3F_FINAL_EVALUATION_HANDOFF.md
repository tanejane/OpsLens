# OpsLens Phase 5.3F — Evaluation Review and UI Design Boundary

## Purpose

This is a **non-invasive evaluation reporting polish**. It does not change the agent,
Gemini prompts, MCP authorization, semantic views, benchmark ground-truth, or the
Phase 5.3E release gate. It analyzes previously generated *live* JSON reports.

## What the latest user-observed results actually show

- Core Gemini regression: **6/7**, all 7 responses observed. Identify the one
  failed case from `phase5_3e_core_live.json` before claiming 7/7.
- Incident probes: **12/12** responses, **12/12** structured-output safety checks.
- Diagnostic incident coverage: **2 measured descriptive**, **9 actionable evidence gaps**,
  **1 other unverified**; **0/12** independently certified incident mechanisms.
- Authoritative Phase 5.3E gate: `PRE_UI_GATE_NOT_PASSED`.

These results support starting UI *concept exploration* later, **not** claiming
all incident investigations work or that deployment has passed acceptance.

## Installation

Merge only `scripts/` and `docs/` into the current OpsLens repository.
No existing file needs replacement. Python stdlib only; no extra requirements.

## Offline review — no Gemini calls

```powershell
python -m scripts.phase5_3f_validate
python -m scripts.phase5_3f_pre_ui_review `
  --core-report .\reports\phase5_3e_core_live.json `
  --incident-report .\reports\phase5_3e_incidents_live.json `
  --gate-report .\reports\phase5_3e_ui_gate.json `
  --output .\reports\phase5_3f_pre_ui_review.json
```

The review reports exact failed core-case IDs and assertion names, per-incident
coverage lists, remaining gates, and UI scope. It **never** converts a planned
investigation into measured evidence or certifies a mechanism by inference.

## Scope for later UI design

**Supported presentation**: bounded KPI requests; supported finance investigations;
delivery/review comparisons; evidence and data-population caveats; explicit
missing-evidence explanations. Label unverified hypotheses as unverified.

**Do not represent as implemented**: seller-level causal analysis, stockout
counterfactuals, verified source-document conflict adjudication, subgroup causal
identification, or autonomous financial writes. Design can show disabled/coming-later
states; it must not promise operations that do not exist.

## Remaining product acceptance actions

1. Fix or explain the **single failing core regression** and rerun the seven-case live suite.
2. Examine the **one `OTHER_UNVERIFIED` incident** and resolve that classification
   honestly; do not count refusal as measurement.
3. Identify whether increasing incident measured coverage from two to three is
   achievable using an already authorized executor; otherwise explicitly adjust
   *scope*, not evidence, through a reviewed release-gate decision.
4. Rerun the original strict Phase 5.3E gate on fresh full live reports. Preserve
   external approval enforcement and independently reviewed mechanism provenance.

## Release interpretation

`REVIEW_COMPLETE_WITH_OPEN_GATES` is a successful *report-generation* outcome,
not product acceptance. Only the existing Phase 5.3E gate can approve scoped UI
implementation under its current criteria. UI *design exploration* itself is
safe to do separately while defects are tracked.
