# P1.1 operational comparison

Added a fixed governed late-versus-on-time order rating comparison over the existing approved delivery/review views. No grants, arbitrary SQL capability or changes to existing calculations were introduced.

## Changes

- `agent/delivery_review_comparison.py`: purchase-cohort compiler, unique-order join, duplicate/alignment/score checks, count and score reconciliation, review coverage, low-rating rates and mean-score difference. Unclassified deliveries and missing reviews remain explicit. Each result carries an evidence ID, methodology, sources and limitations.
- `agent/delivery_review_routing.py`: bounded question routing, month/year resolution and optional Gemini period extraction with independent cross-checking. Model output never becomes SQL. Unsupported deeper follow-ups preserve established findings.
- `agent/session_context.py`: reuse P0.3 context and pending clarification state for comparison follow-ups.
- `scripts/phase5_1_playground.py`: execute through the existing MCP reader and evidence archive; retain execution trace and existing routes.
- `frontend/components/delivery-review-comparison.tsx`, `frontend/app/page.tsx`: question-specific Business KPIs/chart and Analyst cohort table/methodology over the same canonical record. Other investigation presentations remain intact.
- `frontend/lib/report-pdf.ts`: cohort comparison table and methodology in both report modes, alongside the existing complete evidence appendix and canonical attachment.
- `scripts/p1_1_validate.py`, `frontend/tests/comparison.test.mjs`, `frontend/tests/normalize.test.mjs`, `frontend/tests/fixtures/p1_1_comparison.json`: validator, HTTP journey, rendered-view and PDF regression coverage. The captured comparison response comes from the real executor with synthetic external data, not a live measurement.

## Verification

- Existing backend matrix: **79/79 suites passed**, zero failures. Report: `reports/p0_3_offline_validation.json`; run log: `reports/p1_1_regressions.log`.
- P1.1 targeted run: **31/31 tests passed**, including 23 inherited P0.3 tests and eight new comparison tests. Covers missing reviews, overlapping cohorts, invalid grain, period alignment, numeric reconciliation, plan tampering, model-period mismatch, clarification and actual HTTP contextual continuation. See `reports/p1_1_targeted.log`.
- Frontend: **62/62 tests passed**, including server-rendered Business/Analyst figures and PDF preservation. See `reports/p1_1_frontend.log`.
- TypeScript and Next.js production build: passed (`reports/p1_1_typescript.log`, `reports/p1_1_build.log`).
- Live infrastructure check: localhost:5432 refused the connection (Windows 10061). No successful live PostgreSQL, MCP or Gemini execution is claimed. See `reports/p1_1_live_diagnostic.json`.

## Limits

Natural-language support is bounded: delivery lateness plus review/rating terms and an explicit purchase month/year, with supported period follow-ups. Gemini checks the extracted period when enabled; this is not an unrestricted semantic planner. Missing or inconsistent model proposals cannot authorize a query. A follow-up month repeats the cohort analysis for that month; it does not calculate a new cross-month significance test.

Duplicate order IDs or mismatched purchase timestamps reject the comparison instead of guessing how to resolve conflicts. Multiple reviews per order use the pre-existing mean-of-effective-scores policy. Missing delivery timestamps are kept in an unclassified cohort. Missing reviews are excluded only from rating denominators. Results are descriptive, with possible respondent selection and modeled incident adjustments; no causal or statistical-significance claim is made.

The join SQL has not been executed against live PostgreSQL in this environment. Frontend verification uses rendered component tests, not an interactive browser journey. PDF tests verify content and retained canonical evidence; the new report layout has not received visual rendering QA. P0.3's single-worker, process-local session persistence and browser ownership boundary remain unchanged. No enterprise identity system, deeper segmentation or causal attribution was added.
