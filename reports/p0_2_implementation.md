# P0.2 implementation and verification

Implemented `opslens.investigation.v1` across the API, both workspaces and PDF.
The complete original record is retained alongside presentation projections;
validation, arithmetic, Gemini routing and SQL/MCP permissions remain unchanged.

## Repairs

- Adaptive finance retains original metric executor results, the full accounting
  identity, component proofs, all per-order evidence, stage limitations and stop decisions.
- Cross-domain composition retains complete finance/operations children and every
  before/after proof. Cohort audit artifacts and assessments remain available.
- API runtime archives successful validator results and complete MCP envelopes.
  Later execution or cleanup failures retain completed evidence while preserving
  HTTP 503 and a failed overall disposition.
- Normalization handles nested `evidence.measurement`, graph rows,
  `MEASURED_WITH_LIMITATIONS`, `PREMISE_NOT_CONFIRMED` and `adaptive.trace`.
  Before/after denominators stay separate; percentage levels and percentage-point
  changes retain distinct units. No missing value is fabricated.
- Both workspaces inspect the same canonical record. Business summaries remain
  concise; Analyst inspection exposes the entire technical record.
- Both PDFs include the complete evidence appendix and an exact UTF-8 JSON
  attachment. Summaries may format numbers; archive values are not rounded.
  Font-width-based wrapping prevents clipping and preserves long evidence paths.
- One existing semantic-map test had two simultaneous invalid conditions and
  depended on set iteration order. Its fixture now isolates missing relation
  metadata; production validation and rejection assertions were not weakened.

## Verification

| Check | Pass | Fail |
| --- | ---: | ---: |
| Applicable offline backend suites | 78 | 0 |
| Targeted P0.2 tests (included above) | 17 | 0 |
| Frontend tests | 50 | 0 |
| TypeScript `tsc --noEmit` | 1 | 0 |
| Production `next build` | 1 | 0 |
| Independent PDF attachment/layout checks | 2 | 0 |

The shared fixture contains 12 unchanged captured incident responses, one exact
captured metric subtree with a transport wrapper, and six explicitly labeled
synthetic executor cases. Its capture hash is recorded. Coverage includes single
metrics, nested financial measurement/comparison, adaptive, cross-domain,
evidence-gap, premise contradiction and graph results. Additional tests cover
Unicode, precision, unknown fields/versions, rejected validation and failure paths.
Frontend tests compare every canonical record through normalization, both rendered
evidence components and both PDF attachments. Independent pypdf extraction matches
both attachments exactly; pdfplumber checks every page for margin overflow.
Representative summary and appendix pages were also rendered and visually reviewed.

## Remaining boundaries

No information loss was detected in the tested returned-result transformations.
Historical captures that already lack evidence cannot be repaired by inventing it.
Fresh live capture timed out connecting to the configured PostgreSQL service, so
this run does not claim fresh live coverage for all variants or a Gemini end-to-end
run. `scripts.p0_2_capture --live` provides the explicit governed recapture path.
Failures before runtime startup, process termination and transport loss preventing
delivery cannot produce a delivered report; no persistence was added.

## Changed files

### Canonical contract and API

- [agent/investigation_result.py](C:/Users/ejane/Downloads/opslens/agent/investigation_result.py)
- [config/investigation_result.schema.json](C:/Users/ejane/Downloads/opslens/config/investigation_result.schema.json)
- [api.py](C:/Users/ejane/Downloads/opslens/api.py)

### Backend evidence retention

- [agent/phase4c3_investigation.py](C:/Users/ejane/Downloads/opslens/agent/phase4c3_investigation.py)
- [agent/phase4c4_drivers.py](C:/Users/ejane/Downloads/opslens/agent/phase4c4_drivers.py)
- [agent/phase4c7_adaptive.py](C:/Users/ejane/Downloads/opslens/agent/phase4c7_adaptive.py)
- [agent/phase5_2_multidomain.py](C:/Users/ejane/Downloads/opslens/agent/phase5_2_multidomain.py)
- [agent/phase5_2c_three_domain.py](C:/Users/ejane/Downloads/opslens/agent/phase5_2c_three_domain.py)
- [agent/phase5_2f_cohort_evidence.py](C:/Users/ejane/Downloads/opslens/agent/phase5_2f_cohort_evidence.py)

### Request archive and MCP traces

- [agent/phase4b1_semantic_playground.py](C:/Users/ejane/Downloads/opslens/agent/phase4b1_semantic_playground.py)
- [agent/phase4b56_dynamic_period.py](C:/Users/ejane/Downloads/opslens/agent/phase4b56_dynamic_period.py)
- [agent/phase4b57_nl_dynamic_finance.py](C:/Users/ejane/Downloads/opslens/agent/phase4b57_nl_dynamic_finance.py)
- [agent/phase4c2_graph_routing.py](C:/Users/ejane/Downloads/opslens/agent/phase4c2_graph_routing.py)
- [agent/phase4c11_satisfaction.py](C:/Users/ejane/Downloads/opslens/agent/phase4c11_satisfaction.py)
- [agent/phase4c15_delivery.py](C:/Users/ejane/Downloads/opslens/agent/phase4c15_delivery.py)
- [agent/phase4c19_product.py](C:/Users/ejane/Downloads/opslens/agent/phase4c19_product.py)
- [scripts/phase5_1_playground.py](C:/Users/ejane/Downloads/opslens/scripts/phase5_1_playground.py)

### Shared frontend and PDF

- [frontend/app/page.tsx](C:/Users/ejane/Downloads/opslens/frontend/app/page.tsx)
- [frontend/components/investigation-evidence.tsx](C:/Users/ejane/Downloads/opslens/frontend/components/investigation-evidence.tsx)
- [frontend/lib/api-client.ts](C:/Users/ejane/Downloads/opslens/frontend/lib/api-client.ts)
- [frontend/lib/investigation.ts](C:/Users/ejane/Downloads/opslens/frontend/lib/investigation.ts)
- [frontend/lib/report-presentation.ts](C:/Users/ejane/Downloads/opslens/frontend/lib/report-presentation.ts)
- [frontend/lib/report-pdf.ts](C:/Users/ejane/Downloads/opslens/frontend/lib/report-pdf.ts)

### Regression tests and capture tools

- [scripts/p0_2_validate.py](C:/Users/ejane/Downloads/opslens/scripts/p0_2_validate.py)
- [scripts/p0_2_run_offline.py](C:/Users/ejane/Downloads/opslens/scripts/p0_2_run_offline.py)
- [scripts/p0_2_capture.py](C:/Users/ejane/Downloads/opslens/scripts/p0_2_capture.py)
- [scripts/p0_2_pdf_validate.py](C:/Users/ejane/Downloads/opslens/scripts/p0_2_pdf_validate.py)
- [scripts/phase4b4_validate_semantic_map.py](C:/Users/ejane/Downloads/opslens/scripts/phase4b4_validate_semantic_map.py)
- [frontend/tests/normalize.test.mjs](C:/Users/ejane/Downloads/opslens/frontend/tests/normalize.test.mjs)
- [frontend/tests/fixtures/p0_2_variants.json](C:/Users/ejane/Downloads/opslens/frontend/tests/fixtures/p0_2_variants.json)
- [frontend/tests/export-pdf-qa.mjs](C:/Users/ejane/Downloads/opslens/frontend/tests/export-pdf-qa.mjs)

### Contract documentation

- [docs/p0_2_evidence_contract.md](C:/Users/ejane/Downloads/opslens/docs/p0_2_evidence_contract.md)

## Verification artifacts

- [reports/p0_2_offline_validation.json](C:/Users/ejane/Downloads/opslens/reports/p0_2_offline_validation.json)
- [reports/p0_2_frontend_test.log](C:/Users/ejane/Downloads/opslens/reports/p0_2_frontend_test.log)
- [reports/p0_2_typescript.log](C:/Users/ejane/Downloads/opslens/reports/p0_2_typescript.log)
- [reports/p0_2_build.log](C:/Users/ejane/Downloads/opslens/reports/p0_2_build.log)
- [reports/p0_2_pdf_validation.json](C:/Users/ejane/Downloads/opslens/reports/p0_2_pdf_validation.json)
