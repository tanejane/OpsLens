# Frontend failure review and minimal cleanup

Continuation of the 2026-11-10 audit; no new full repository inventory.

## Failure-by-failure diagnosis

| Original test | Root cause and resolution |
|---|---|
| 8: timeline and replay are optional Analyst-only diagnostics | Obsolete Analyst-only visibility/raw-tool-name expectations. Unified UI intentionally exposes collapsed diagnostics in both legacy modes; assert equal output, friendly labels, replay and chronology caveat. |
| 28: business and analyst PDF exports are valid non-empty PDFs with facts and limitations | Unconditional validation-proposal expectation was obsolete when no specific recommendation is returned. Also exposed a real PDF omission: finance premise deltas were absent from visible measurements. Restore signed deltas and assert exact attachment, currency and causal limits. |
| 29: three-domain and single-domain reports format titles, measures, audited evidence and provenance | Old Key Metrics/title and same-page provenance expectations no longer match the answer-first layout. Assert current sections and retained source/denominator values without arbitrary pagination coupling; finance values restored. |
| 30: three-domain PDF preserves the supplied finance, delivery, review and cohort audit values | Old Direct Answer and Verified Premise heading. Retain direct-answer ordering and numerical/cohort assertions; restore accounting sources and comparison/delta units in PDF output. |
| 43: P0.2 captured_INC_001: API, normalization, both workspaces and both PDF attachments preserve every value | Obsolete requirement to print every canonical JSON path/scalar as report pages. Keep all UI evidence assertions and exact decoded PDF attachment equality; require readable direct answer and attachment notice. |
| 44: P0.2 captured_INC_002: API, normalization, both workspaces and both PDF attachments preserve every value | Obsolete requirement to print every canonical JSON path/scalar as report pages. Keep all UI evidence assertions and exact decoded PDF attachment equality; require readable direct answer and attachment notice. |
| 45: P0.2 captured_INC_003: API, normalization, both workspaces and both PDF attachments preserve every value | Obsolete requirement to print every canonical JSON path/scalar as report pages. Keep all UI evidence assertions and exact decoded PDF attachment equality; require readable direct answer and attachment notice. |
| 46: P0.2 captured_INC_004: API, normalization, both workspaces and both PDF attachments preserve every value | Obsolete requirement to print every canonical JSON path/scalar as report pages. Keep all UI evidence assertions and exact decoded PDF attachment equality; require readable direct answer and attachment notice. |
| 47: P0.2 captured_INC_005: API, normalization, both workspaces and both PDF attachments preserve every value | Obsolete requirement to print every canonical JSON path/scalar as report pages. Keep all UI evidence assertions and exact decoded PDF attachment equality; require readable direct answer and attachment notice. |
| 48: P0.2 captured_INC_006: API, normalization, both workspaces and both PDF attachments preserve every value | Obsolete requirement to print every canonical JSON path/scalar as report pages. Keep all UI evidence assertions and exact decoded PDF attachment equality; require readable direct answer and attachment notice. |
| 49: P0.2 captured_INC_007: API, normalization, both workspaces and both PDF attachments preserve every value | Obsolete requirement to print every canonical JSON path/scalar as report pages. Keep all UI evidence assertions and exact decoded PDF attachment equality; require readable direct answer and attachment notice. |
| 50: P0.2 captured_INC_008: API, normalization, both workspaces and both PDF attachments preserve every value | Obsolete requirement to print every canonical JSON path/scalar as report pages. Keep all UI evidence assertions and exact decoded PDF attachment equality; require readable direct answer and attachment notice. |
| 51: P0.2 captured_INC_009: API, normalization, both workspaces and both PDF attachments preserve every value | Obsolete requirement to print every canonical JSON path/scalar as report pages. Keep all UI evidence assertions and exact decoded PDF attachment equality; require readable direct answer and attachment notice. |
| 52: P0.2 captured_INC_010: API, normalization, both workspaces and both PDF attachments preserve every value | Obsolete requirement to print every canonical JSON path/scalar as report pages. Keep all UI evidence assertions and exact decoded PDF attachment equality; require readable direct answer and attachment notice. |
| 53: P0.2 captured_INC_011: API, normalization, both workspaces and both PDF attachments preserve every value | Obsolete requirement to print every canonical JSON path/scalar as report pages. Keep all UI evidence assertions and exact decoded PDF attachment equality; require readable direct answer and attachment notice. |
| 54: P0.2 captured_INC_012: API, normalization, both workspaces and both PDF attachments preserve every value | Obsolete requirement to print every canonical JSON path/scalar as report pages. Keep all UI evidence assertions and exact decoded PDF attachment equality; require readable direct answer and attachment notice. |
| 55: P0.2 single_metric: API, normalization, both workspaces and both PDF attachments preserve every value | Obsolete requirement to print every canonical JSON path/scalar as report pages. Keep all UI evidence assertions and exact decoded PDF attachment equality; require readable direct answer and attachment notice. |
| 56: P0.2 adaptive: API, normalization, both workspaces and both PDF attachments preserve every value | Obsolete requirement to print every canonical JSON path/scalar as report pages. Keep all UI evidence assertions and exact decoded PDF attachment equality; require readable direct answer and attachment notice. |
| 57: P0.2 premise_contradiction: API, normalization, both workspaces and both PDF attachments preserve every value | Obsolete requirement to print every canonical JSON path/scalar as report pages. Keep all UI evidence assertions and exact decoded PDF attachment equality; require readable direct answer and attachment notice. |
| 58: P0.2 cross_domain: API, normalization, both workspaces and both PDF attachments preserve every value | Obsolete requirement to print every canonical JSON path/scalar as report pages. Keep all UI evidence assertions and exact decoded PDF attachment equality; require readable direct answer and attachment notice. |
| 59: P0.2 operational: API, normalization, both workspaces and both PDF attachments preserve every value | Obsolete requirement to print every canonical JSON path/scalar as report pages. Keep all UI evidence assertions and exact decoded PDF attachment equality; require readable direct answer and attachment notice. |
| 60: P0.2 financial: API, normalization, both workspaces and both PDF attachments preserve every value | Obsolete requirement to print every canonical JSON path/scalar as report pages. Keep all UI evidence assertions and exact decoded PDF attachment equality; require readable direct answer and attachment notice. |
| 61: P0.2 graph: API, normalization, both workspaces and both PDF attachments preserve every value | Obsolete requirement to print every canonical JSON path/scalar as report pages. Keep all UI evidence assertions and exact decoded PDF attachment equality; require readable direct answer and attachment notice. |
| 67: adaptive findings and traces survive both PDF modes | Old printed orchestration/supporting-analysis details expectation. Verify the complete exact record (including all findings and stop reasons) in each PDF attachment and readable answer/trace notice. |
| 69: document conflicts and passages survive normalization and PDF modes | Old printed document-passage scalar expectation. Verify exact attached record and visible corroboration/conflict labels. Fix misleading evidence-appendix wording: passages are in the JSON attachment. |
| 80: Business/Analyst switching shares the controller and only changes presentation | Removed global Business/Analyst toggle and whitespace-sensitive source regex. Assert the intentional fixed Business presentation, single session controller, explicit reset and absence of automatic replay; runtime session tests unchanged. |

## Production change scope

Only `frontend/lib/report-pdf.ts` changed executable behavior: restored finance premise deltas, comparison units/delta units and accounting provenance; corrected attachment wording. The answer-first UI and backend remain unchanged. Tests were updated in the three existing files; no test removed, skipped or disabled.

## Deleted artifacts

Current frontend counterparts remain. Installed patch markers (`financeExecutiveSummary`, `financeGuidance`, unified workspace) were verified. No remaining source/config/test references to the candidates; references from patch writers were outputs, not runtime reads. TS backups were incidentally scanned by TypeScript, not imported app routes. Hashes were recorded and verified immediately before individual deletion.

- `opslens_answer_first_patch.py` — Superseded one-time frontend source patch; installed markers confirmed.
- `opslens_presentation_refinement.py` — Superseded one-time frontend source patch; installed markers confirmed.
- `frontend/app/page.backup-20261107-133850.txt` — Obsolete frontend rollback copy; current counterpart retained, no runtime imports; only patch-output references.
- `frontend/app/page.backup-20261107-164432.txt` — Obsolete frontend rollback copy; current counterpart retained, no runtime imports; only patch-output references.
- `frontend/app/page.before-evidence-redesign.txt` — Obsolete frontend rollback copy; current counterpart retained, no runtime imports; only patch-output references.
- `frontend/app/page.before-gemini-repair-20261107-234015.txt` — Obsolete frontend rollback copy; current counterpart retained, no runtime imports; only patch-output references.
- `frontend/app/page.before-gemini-repair-20261107-234719.txt` — Obsolete frontend rollback copy; current counterpart retained, no runtime imports; only patch-output references.
- `frontend/app/page.before-interpretation-cleanup-20261107-232220.txt` — Obsolete frontend rollback copy; current counterpart retained, no runtime imports; only patch-output references.
- `frontend/app/page.before_presentation_refinement.tsx` — Obsolete frontend rollback copy; current counterpart retained, no runtime imports; only patch-output references.
- `frontend/components/investigation-timeline.backup-20261108-111750.txt` — Obsolete frontend rollback copy; current counterpart retained, no runtime imports; only patch-output references.
- `frontend/lib/report-presentation.before_answer_first.ts` — Obsolete frontend rollback copy; current counterpart retained, no runtime imports; only patch-output references.
- `frontend/lib/report-presentation.before_refinement.ts` — Obsolete frontend rollback copy; current counterpart retained, no runtime imports; only patch-output references.
- `scripts/fix_unified_page.py` — Superseded one-time frontend source patch; installed markers confirmed.
- `scripts/opslens_answer_first_patch.py` — Superseded one-time frontend source patch; installed markers confirmed.

## Preserved and reproducibility

All backend rollback files, audit archives, replay data, reports, fixtures and regression tests remain. README_APPLY.md remains as integration history. Python/Node dependencies were not upgraded or removed. Root/frontend README now document the unified workspace, expiring owner-bound sessions, exact PDF attachments, npm ci, provisioning prerequisites, optional Gemini and validation.

Local pip check passed. Frontend package/lock root dependency lists agree; npm dependency-tree validation and build results are recorded below. Python requirements are ranges, not a lock; phase2d declares pytest 8 but the installed test runner is 9.2.0. The documentation identifies this drift instead of silently rewriting dependency constraints. A fresh environment and ignored dataset acquisition remain prerequisites to full reproducibility.

## Validation

- Frontend: all 81 existing tests passed after fixes and deletion; none skipped or disabled.
- TypeScript: `npx tsc --noEmit --incremental false` passed.
- Production build: `npm run build` passed; existing unused-variable warnings remain in page/PDF code.
- Focused backend: 32 tests passed (cohorts, SQL boundaries/policy, trace projection). No backend changes; hashes match the prior audit.
- Full async/backend and live PostgreSQL/Gemini gates not rerun. Prior Windows asyncio socket-pair blocker remains unresolved.
- PDF fixtures: both generated successfully. PDF attachment equality is exercised across all existing regression fixtures. Independent pypdf/pdfplumber layout validation was not run because those optional tools are absent; visual layout was not certified.
- Python dependency check: no broken requirements.
- Node manifest/lockfile: dependency lists agree; `npm ls --depth=0` exits successfully but reports two extra local packages (`@emnapi/runtime`, `@img/sharp-wasm32`). Dependencies were preserved; use documented `npm ci` in a fresh checkout. No fresh install was performed.
- Generated tracked metadata restored after build; existing user changes preserved. No commit, push or deployment.
