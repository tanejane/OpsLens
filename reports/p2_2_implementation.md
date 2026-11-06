# P2.2 verification

Implemented bounded SQLite trace snapshots, credential redaction, content-addressed
evidence references, tool latency/outcomes, available model usage, owner/session-bound
deterministic replay, graceful trace-storage failure handling and optional Analyst
timeline/replay access. Business findings and governed analytical paths remain intact.

Implementation/file details: `docs/p2_2_observability.md`.

## Results

| Focused suite | Passed | Failed |
|---|---:|---:|
| P2.2 trace/HTTP/replay | 6 | 0 |
| P0.2 canonical evidence | 17 | 0 |
| P0.3 sessions | 23 | 0 |
| P2.1 documents | 10 | 0 |
| P1.2 adaptive | 10 | 0 |
| Finance interpreter checks | 23 | 0 |
| Routing checks | 22 | 0 |
| Frontend tests | 71 | 0 |

TypeScript and the final production build passed (`p2_2_build.log`).
The full historical 79-suite matrix was intentionally not repeated.

Tests cover durable store reopening, exact canonical replay equality, integrity
failure, owner/session isolation, expiration/reset, bounded retention, redaction,
tool timeout records, failed-run replay without corrupting validated context,
disk-failure retention, request-local model metadata, Analyst-only diagnostics,
and preservation in both PDF modes. HTTP replay was executed with the analytical
execution function patched to fail if called; no model/MCP/database calls occurred.

Two initial new-test errors were corrected: a wrong evidence-field path and an
unclosed SQLite connection in the tampering test. The existing canonical regression
also detected a stateless response-contract change; implementation was corrected
to keep persistence session-scoped without changing the regression assertion.

## Limits

- Saved replay requires an active owner-authorized session. Existing process-local
  sessions do not survive server restart, even though SQLite traces persist.
- Local storage relies on private filesystem access controls; it is not encrypted
  enterprise audit storage. Expiration cleanup runs on store access.
- Model usage is captured in routing, finance-intent and semantic-intent adapters
  when returned. Other paths or absent provider fields remain unknown.
- Replay returns saved evidence JSON, not a fresh analytical execution or a claim
  that underlying data is unchanged. Stateless legacy calls have no saved run.
- No live Gemini/PostgreSQL or browser visual-layout verification was performed
  for P2.2. No existing database contents were modified.
