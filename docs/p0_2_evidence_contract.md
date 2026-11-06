# P0.2 investigation evidence contract

`opslens.investigation.v1` is defined in `config/investigation_result.schema.json`.
It contains the question and a complete `payload` snapshot of the executor result.
It is a transport contract, not a new validation or authorization decision.
Unknown payload and envelope fields must survive normalization and export.

The API returns `canonical_result`; `result` remains its payload alias for legacy
clients. Both workspaces and both PDF modes consume the same canonical record.
The normalizer provides presentation projections without modifying that record.
Older unversioned results are wrapped locally. Unknown contract versions retain
their record but are presented as unverified.

Values, source IDs, units, periods, eligibility policies and denominator proofs
remain at their original scope. No population is copied from the before period
to a shared population. Finance and operations keep independent child results.
Decimal values and integers outside JavaScript's safe range are encoded as exact
strings with their original numeric kind recorded by JSON Pointer in
`number_encodings`. Existing finite floats retain their supplied precision; the
contract cannot recover precision lost before execution returned a value.

## Active variants and projections

| Executor result | Presentation projection | Complete evidence retained |
| --- | --- | --- |
| Direct operational/product metric | `evidence.value` | Entire source evidence, policies, populations and limitations |
| Finance measure/comparison | `evidence.measurement`, `evidence.before`, `evidence.comparison` | Full measurements, audit checks, absolute/relative changes |
| Operational comparison | `before`, `after`, `delta` | Independent before/after proofs |
| Graph `MEASURED_WITH_LIMITATIONS` | Dimensioned `evidence.rows` | All rows, source relations, relationship IDs, limits and safety metadata |
| Core/adaptive finance | Premise, original metrics, accounting bridge, ranked hypotheses, per-order context | Full `metric_results`, stage results, all component proofs, adaptive decisions and stop reason |
| Cross-domain synthesis | Operational changes plus financial metrics | Full `measurements`, `beforeEvidence`/`afterEvidence`, `domain_results`, cohort artifact and assessment |
| `PREMISE_NOT_CONFIRMED` | Explicit contradiction, observed metrics | Measured proof and stop reason; no causal or driver claim |
| Partial/gap/refusal/failure | Original disposition and evidence requirements | Original returned fields; absence is never replaced with zero |

Current limitations appear in the summary. Original stage caveats remain under
their stage path, even when later component reconciliation supersedes them.
MCP envelopes and app-owned query arguments are retained in the API runtime's
execution trace; recording does not change SQL or grant query permissions.
Successful finance, delivery, review, product, graph and component validator
returns are also retained in a request-local `validated_evidence` archive. A
later rejection does not erase those independently completed steps or upgrade
the failed overall disposition. An execution exception keeps HTTP 503 and carries
an `EXECUTION_FAILED` canonical record; the UI error and evidence report coexist.

## Presentation and PDF

Business summaries remain concise. Analyst evidence inspection opens the full
technical record by default inside Evidence & Methodology. Both modes include
the same complete path/value record, including fields unknown to the summaries.
Paths are JSON Pointers, not fabricated source evidence IDs.

Both PDF modes include all limitations, per-order evidence, graph rows, the full
accounting identity when supplied, and a complete path/value appendix. Appendix
values are not rounded; Unicode uses reversible JSON escapes in the existing
Helvetica font. The embedded `opslens-investigation.json` attachment preserves
the original Unicode and exact canonical JSON, independent of summary formatting.

## Verification and boundaries

`scripts.p0_2_validate` checks unchanged captured incident responses and production
composers. `frontend/tests/fixtures/p0_2_variants.json` records the capture hash and
labels every generated executor case as synthetic. Frontend tests render both
workspaces' shared evidence component, inspect PDF text and compare each embedded
record exactly with the backend-generated API response. Existing safety tests
remain in force. `scripts.p0_2_run_offline` runs all applicable offline suites.

`scripts.p0_2_capture --live` is an explicit read-only recapture tool for configured
MCP/PostgreSQL; fixed interpretations avoid Gemini calls. Fresh capture was blocked
by the local database connection during this implementation. Existing captures
cannot recover fields discarded before they were saved. Failures before runtime
startup, connection loss preventing delivery, and process termination cannot
produce a delivered investigation record. No persistence or fabricated evidence
is introduced for those cases.
