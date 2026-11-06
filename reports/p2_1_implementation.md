# P2.1 implementation and verification

## Changed files

- `agent/document_corroboration.py`: conditional governed retrieval coordination,
  source validation, exact scoped numerical comparison, conflicts, partial results.
- `agent/session_context.py`, `scripts/phase5_1_playground.py`: contextual document
  follow-ups, existing budget integration, canonical and bounded history retention.
- `frontend/components/document-evidence.tsx`, `frontend/app/page.tsx`: shared
  Business/Analyst document presentation across existing report variants.
- `frontend/lib/report-pdf.ts`: document cross-check section with complete evidence
  retained by the existing canonical appendix/attachment.
- `scripts/p2_1_validate.py`, `scripts/p2_1_live.py`: offline/HTTP and live checks.
- `frontend/tests/normalize.test.mjs`, `frontend/tests/comparison.test.mjs`,
  `frontend/tests/fixtures/p2_1_documents.json`,
  `frontend/tests/fixtures/p2_1_live_documents.json`: scoped claim fixtures, real
  repository passages and a captured live response; normalization/view/PDF checks.
- `docs/p2_1_document_contract.md`: contract and explicit limits.

## Verification

- Initial legacy backend matrix: 79/79 suites passed. Final rerun: 78/79 passed;
  `validate_phase3e_imports` exceeded its 120-second timeout during concurrent build
  work. The isolated retry passed all three import checks (`p2_1_import_retry.log`).
  No outstanding assertion failure; the full final matrix was not rerun again.
- P1.1: 31/31 tests; P1.2: 10/10; P1.3: 10/10; checkpoint regressions: 8/8.
- P2.1: 10/10, including actual FastAPI endpoints with mocked external boundaries,
  no repeated SQL for document follow-ups, session retention, four-check bound,
  matching/conflicting claims, incompatible populations, stale/future versions,
  missing metadata, malicious passages, conditional retrieval and partial failure.
- Frontend: 69/69, including captured live canonical equality after normalization
  and exact PDF attachment round trips in both modes.
- TypeScript and production build passed. No browser visual-layout certification.

Logs are `reports/p2_1_*.log`; backend matrix details are in
`reports/p0_3_offline_validation.json`.

## Actual live trace

`reports/p2_1_live.json` records real HTTP/Gemini/MCP/PostgreSQL and hybrid retrieval,
without mocks or dataset writes:

1. March versus February 2018 revenue/profit divergence: HTTP 200, 64.958 seconds,
   16 `run_readonly_sql` calls, validated noncausal investigation.
2. "Cross-check that with documents": HTTP 200, 6.248 seconds, one internal-trust
   `search_knowledge` call, no SQL rerun. Original canonical record equality verified.
   Five passages: campaign brief context; incomplete finance note and preliminary
   operations summary provisional; supplier notice and corrected operations summary
   irrelevant to the bounded query matching. No numerical corroboration or conflict
   was established from these live prose passages. Forty-two existing measurement
   objects were indexed for comparison; none were invented from documents.

The final live run includes the corrected status-field classifier. The subsequent
four-check history bound was verified through offline HTTP tests, not a second live
four-turn run. Live numerical agreement/conflict is not claimed: those cases use
explicitly labeled offline scoped-claim fixtures.

## Remaining limitations

General prose is retained as context; automated numerical comparison requires
explicit, fully scoped Measurement JSON. Lexical relevance can miss related terms.
The current corpus/index cannot certify document dates or current versions.
Prose-to-prose contradictions and causal adjudication are not implemented.
Retrieval is explicitly requested, not automatically triggered by every evidence
gap. Source filtering is defense in depth, not a universal injection classifier;
untrusted text cannot issue tool instructions. Existing process-local session
storage and enterprise-authentication limitations remain unchanged.
