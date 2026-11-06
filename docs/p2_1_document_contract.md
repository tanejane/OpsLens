# P2.1 document corroboration contract

The canonical P0.2 payload gains `document_evidence` with schema version
`opslens.document-corroboration.v1`. Existing measurements are unchanged.
Each assessed source retains the original retrieval hit, passage, document/chunk
identity, date, trust, retrieval scores, content hash, declared version, disposition,
and comparison records. Comparisons link to database JSON paths and original values.
Neither retrieval nor a matching claim establishes causation.

## Execution

An explicit document/corroboration request on an executable, noncausal governed
result triggers the registered MCP `search_knowledge` tool, internal trust filter,
and at most five passages. Existing hybrid retrieval and security filtering run
unchanged. An additional local check treats returned text as data; it is never
passed to Gemini as instructions or executed. The shared investigation deadline,
step/tool budgets, and action deduplication apply. Failures retain database findings.

Bounded contextual phrases such as "Cross-check that with documents" reuse the
session's validated canonical record without rerunning SQL. The original record
is retained in `database_record`; three previous document checks and their tool
traces are retained in `document_check_history`. At four checks, retrieval stops
and the existing evidence is retained, with an explicit new-investigation notice.
Existing session ownership, expiration and size limits remain in force.

## Validation and limitations

Missing provenance/date, future dates, untrusted sources, injection indicators and
irrelevant passages cannot corroborate measurements. Provisional status is read
from title/status fields, not historical mentions in approved corrections.
Declared integer versions are compared only within the same document identity
and only among eligible retrieved hits. The index has inferred dates and no
authoritative version registry; this implementation cannot certify currency.

Numerical comparison supports explicit `Measurement: {JSON}` lines with exactly
matching `metric_id`, `period`, `source`, `unit`, and a nonempty `population` object.
Finite decimal values are compared without floating-point tolerance. Conflicting
database values yield ambiguity; a claim dated before period close cannot confirm
a final measurement. Other prose remains labeled context, never a fabricated
measurement or causal explanation. Relevance is bounded lexical overlap, not a
semantic claim verifier. Conflicts between unstructured prose are not adjudicated.

Business presentation shows concise source context and qualified outcomes.
Analyst presentation exposes passages, provenance, versions and comparisons.
Both PDF modes preserve the complete canonical attachment/evidence appendix.
No new SQL capability, MCP permission, schema, dataset or dependency is introduced.
