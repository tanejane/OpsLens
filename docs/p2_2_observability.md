# P2.2 observability and saved-evidence replay

Session investigation results retain the existing canonical schema and gain
`payload.observability`: an opaque run ID, elapsed milliseconds, validation
decision, content-addressed validated-evidence IDs and paths, stop reason,
persistence availability and available model usage. Existing execution traces,
validated results, source references, document conflicts and numerical encodings
remain in the same canonical record. MCP calls now include elapsed time and
returned/rejected/failed outcomes; failed calls retain only exception types.
Routing, finance-intent and semantic-intent adapters record returned model/version
and token metadata in a request-local collector; missing metadata is unknown.

## Persistence and access

`investigation_traces.TraceStore` uses SQLite at
`.runtime/investigation-traces.sqlite3` (override with `OPSLENS_TRACE_DB`). The
runtime directory is excluded from version control. Defaults: 30-minute lifetime,
8 runs per session, 256 runs globally, 2 MB per record and 32 MB logical data.
SQLite allocated pages are also bounded with overhead allowance. Oldest records
are evicted to enforce limits. Expired rows are securely deleted on the next store
operation; there is no background purge scheduler. Database connections close
after each operation. Files use restrictive modes on POSIX; Windows deployments
must retain the private application directory's inherited ACL. This is local
storage, not encrypted enterprise audit infrastructure.

Records are redacted before persistence and session publication: sensitive fields,
known credential environment values, bearer tokens, credential assignments and
credential-bearing URLs. Analytical numbers, token counts and provenance survive.
Arbitrary unknown secrets cannot be reliably recognized; avoid placing credentials
in business data. No prompts or raw provider exceptions are added to model traces.

`GET /api/investigation-sessions/{session_id}/runs/{run_id}/replay` requires the
existing owner cookie and an active authorized session, then checks both session
and owner binding in SQLite. A run ID or session ID alone is insufficient. Responses
are no-store. Reset revokes session access and purges its rows; a failed purge
cannot restore access. Session expiration revokes access regardless of trace TTL.

The saved canonical JSON is SHA-256 checked before returning. Replay returns that
exact record plus a separate replay envelope and performs zero Gemini/MCP/SQL
analytical calls. It is deterministic evidence replay, not recomputation against
current data. The checksum detects corruption, not a malicious local administrator
who can rewrite both record and checksum. Trace persistence survives reopening the
store, but existing process-local session authorization does not survive backend
restart; no bypass of that boundary is added. Legacy stateless calls retain their
prior response contract and do not create saved runs.

## Failure and presentation behavior

Existing deadlines, budgets and partial-result retention remain in force, with no
new retries. Failed session turns get a noncertified saved record where returned;
previous validated session context remains intact. Audit storage failure reports
`UNAVAILABLE` without replacing completed findings. Replay refuses missing,
expired or corrupt records rather than running the investigator again.

Analyst View adds a collapsed timeline with execution steps, tool outcomes,
validation references, model metadata and a link to the saved JSON replay.
Business View hides the new diagnostics. Both modes preserve the canonical record
in PDF attachments. There is no UI redesign or new analytical permission.

## Changed implementation and tests

- `investigation_traces.py`, `api.py`, `.gitignore`: storage, redaction, metadata,
  session integration, authorized replay and reset handling.
- `scripts/phase5_1_playground.py`: request-local model metadata alongside evidence.
- `agent/phase4b1_semantic_playground.py`: MCP latency/failure tracing.
- `agent/phase4c1_router.py`, `agent/phase4b57_nl_dynamic_finance.py`,
  `agent/phase4b44_gemini_interpreter.py`: provider-returned model usage capture.
- `frontend/components/investigation-timeline.tsx`,
  `frontend/components/investigation-evidence.tsx`, `frontend/app/page.tsx`:
  optional Analyst diagnostics with unchanged primary Business findings.
- `scripts/p2_2_validate.py`, frontend comparison/normalization tests: integrity,
  exact replay, isolation, redaction, retention, timeout and storage-failure
  handling, request-local model usage, view separation and PDF preservation.

Verification logs: `reports/p2_2_*.log`. Focused tests are offline, with actual
FastAPI endpoints and mocked external analytical boundaries. No new live Gemini
or PostgreSQL execution was performed for P2.2, and no database dataset was changed.
