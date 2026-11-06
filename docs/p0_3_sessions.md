# Persistent investigation context (P0.3)

The frontend creates an owned server session and reuses the existing recovery stack across turns. It keeps only an opaque session ID in sessionStorage; Business and Analyst views share the same canonical result. Switching views changes presentation only. New investigation deletes the server session before clearing local state. Reload restores the latest record without executing Gemini or MCP.

## HTTP contract

- `POST /api/investigation-sessions` returns `{session}` and sets an independent HttpOnly owner credential.
- `GET /api/investigation-sessions/{id}` restores history, revision, last validated result and clarification state.
- `POST /api/investigations` accepts `{question, session_id, revision}`. It returns the existing P0.2 envelope plus a session snapshot. Calls without a session ID remain supported for existing clients.
- `DELETE /api/investigation-sessions/{id}` revokes the session.

Unknown, expired and differently owned sessions return the same 404. Concurrent or stale turns return 409; the client may refresh state but never automatically replays tools. Missing revisions return 422. Capacity returns 429; evidence exceeding storage limits returns 413 with the completed canonical result retained in the error envelope. Previous validated state remains unchanged. Execution errors with partial canonical evidence retain it in turn history but do not replace validated analytical context.

## Context and governance

`agent/session_context.py` resolves bounded references using existing RecoverySession state and the last validated canonical record. It records original/resolved questions, inherited fields, source turn and pending source turn. Explicit periods/metrics take precedence; ambiguous years or baselines require clarification. Existing delivery, graph, product and finance execution paths retain their validators and permissions.

For example, “Why did profit decline in March 2018?” requests a comparison baseline; “Compare that with February” inherits March's year and runs the governed contribution-profit comparison. This measures the premise, not causation. Marketing drill-down reuses any retained accounting proof with its full source record and explicitly reports the missing finer-grained capability. It does not invent campaign/channel attribution or issue new SQL. Supported corrections and cancellation use the existing recovery components; unsupported ambiguous follow-ups remain clarifications.

The session commits cloned recovery state only after a validated executable outcome. Safe clarifications commit pending slots only. Rejections, execution failures and storage failures cannot overwrite the previous validated context. Canonical payloads, numeric encoding metadata, evidence IDs, populations, limitations and traces are preserved.

## Retention and deployment boundary

Default storage: 30-minute idle TTL, 64 sessions per process, eight recent turns, two million serialized bytes per session and 32 million globally. The last validated result remains separately available when older turns are evicted; snapshots expose eviction counts. Cleanup occurs on session access/creation. In-flight requests retain their lock until the isolated worker finishes.

This is bounded **process-local persistence**, not durable database storage. Deploy one API worker; restart loses sessions and multiple workers do not share state. Recovery objects are bounded structured context, not a transcript injected into Gemini. The frontend's New investigation action is required after expiration rather than silently discarding context.

Session IDs are not authentication. Access also requires the separate random owner cookie, stored hashed on the server. Cookies are HttpOnly, SameSite Strict and Secure for HTTPS (or `OPSLENS_COOKIE_SECURE=1`). Mutating endpoints check Origin and cross-site fetch metadata; configure `OPSLENS_FRONTEND_ORIGIN` for deployment. The Next.js proxy forwards the cookie and origin, and session responses disable caching. This browser ownership boundary is not enterprise identity, tenant authorization or protection from same-origin compromise. Enterprise deployment still requires authenticated ownership and a shared durable store.

## Verification commands

Run from repository root: `python -B -m scripts.p0_3_validate` and `python -B -m scripts.p0_3_run_offline`. From `frontend`: `npm test`, `npx tsc --noEmit`, `npm run build`.

HTTP tests use FastAPI TestClient with real session/recovery/execution/validation code and mocked external model/MCP responses. They are offline tests, not evidence of live Gemini or PostgreSQL availability.
