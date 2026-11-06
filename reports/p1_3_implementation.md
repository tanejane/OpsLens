# P1.3 seller concentration

Implemented a governed seller delivery investigation. An explicit seller/delivery question first measures the approved delivery population. The adaptive coordinator requests the seller partition only if validated late orders exist. No late orders means no additional seller query. Failed seller analysis retains the original delivery findings.

## Attribution and schema decision

Inspected the semantic relationship map, item evidence/audit definitions and delivery/review view contracts. `commerce.order_items` contains seller IDs at item grain; the delivery view is order grain, and review scores are aggregated at order grain. Seller names, fulfillment responsibility and seller-level review attribution are not inferred.

Items are grouped by order before joining delivery evidence. Repeated item rows for the same seller do not multiply orders. Exactly one distinct known seller permits inclusion in the seller ranking. Any missing seller ID or absent item mapping produces an unknown bucket. More than one distinct known seller produces a multi-seller bucket. Missing seller data takes precedence over the multi-seller label. These buckets partition orders without overlap; no shared order is assigned fractionally or counted under multiple sellers.

Counts reconcile at three levels: overall validated delivery population, attribution buckets and exclusive seller totals. Eligible means actual and promised delivery dates exist. Late rate is seller late orders / seller eligible orders. Concentration share is seller late orders / all single-seller late orders. These denominators are explicitly distinct. Duplicate delivery IDs, repeated seller output IDs, invalid counts, mismatched periods and inconsistent totals reject the seller proof.

## Changed files

- `agent/seller_concentration.py`: fixed read-only SQL, validation, evidence IDs, seller rates/shares and attribution partitions.
- `agent/seller_routing.py`: bounded natural-language and contextual period resolution; unsupported seller review/financial requests remain unsupported.
- `agent/session_context.py`: seller clarification and follow-up integration with P0.3.
- `agent/evidence_followup.py`: evidence-and-intent-gated seller action, validated conclusions and partial-failure retention.
- `scripts/phase5_1_playground.py`: existing Gemini period cross-check, MCP reader, canonical archive and budget integration.
- `frontend/components/seller-concentration.tsx`, `frontend/app/page.tsx`: shared-record Business chart/rates and Analyst full seller table, populations, methodology and trace. Business displays the top ten; complete rows remain available in Analyst and canonical evidence.
- `frontend/lib/report-pdf.ts`: seller table and explicit attribution buckets, retaining the existing canonical attachment and evidence appendix.
- `scripts/p1_3_validate.py`, `frontend/tests/comparison.test.mjs`, `frontend/tests/normalize.test.mjs`, `frontend/tests/fixtures/p1_3_seller.json`: seller correctness, HTTP follow-up, rendered views and PDF/canonical preservation. Fixture captured from the real offline coordinator with synthetic external rows.

## Verification

- Seller tests: 10/10 passed, including actual FastAPI HTTP session continuation.
- Existing adaptive acceptance: 10/10 passed.
- P1.1/P0.3 HTTP/regression tests: 31/31 passed.
- Existing backend matrix: 79/79 suites passed.
- Frontend: 66/66 passed; TypeScript and production build passed.
- Logs: `reports/p1_3_targeted.log`, `reports/p1_3_adaptive.log`, `reports/p1_3_http.log`, `reports/p1_3_regressions.log`, `reports/p1_3_frontend.log`, `reports/p1_3_typescript.log`, `reports/p1_3_build.log`.

## Limits

Local PostgreSQL refused connections (10061); no live SQL, MCP or Gemini success is claimed (`reports/p1_3_live_diagnostic.json`). SQL execution against actual PostgreSQL remains unverified. Offline tests validate the compiler/aggregate contracts and real HTTP path with mocked external rows; they do not independently prove the SQL on live source records.

Seller association is not responsibility or causation. Multi-seller and unknown orders can account for substantial late-order volume; the ranking intentionally excludes them and reports their scale. Rates are descriptive, without significance tests or small-sample certification. Item seller IDs are shown without invented names. Seller-level review and financial comparisons are not registered.

The two reads reconcile aggregate populations but do not establish a transactionally frozen database snapshot. More than 5,000 seller rows rejects the extension while preserving the initial result. Existing execution budgets, session size limits, process-local persistence and browser ownership boundary remain unchanged. Frontend verification uses rendered component tests; PDF tests check content/evidence, not visual layout QA.
