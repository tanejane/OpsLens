# Live integration checkpoint — 3 November 2026 (Asia/Kuala_Lumpur)

The final five-turn journey completed against the existing PostgreSQL database through the running Next.js proxy, FastAPI, real Gemini interpretation, governed MCP, validators and canonical session results. No datasets, database contents or database permissions were changed.

## Authentication and environment

The updated key passed one minimal provider request: `OK`, 7.062 seconds. Credentials were loaded from `.env` without displaying their values. A scan of checkpoint logs/artifacts found zero occurrences of the configured credential values.

Docker had stopped because its runtime socket `sailor-ingest.sock` was inaccessible. Ordinary start/restart and single-socket move/removal failed. After stopping hung Docker processes, the runtime-only directory `C:\Users\ejane\AppData\Local\Docker\run` was reversibly moved to `run.checkpoint-stale`. Its four entries were runtime sockets/reparse points, not database data. Docker recreated the runtime directory and restarted the existing healthy `opslens-postgres` container using `opslens_opslens_pgdata`. No factory reset, volume recreation, migration or dataset reload was performed. Existing commerce coverage: 99,441 orders, September 2016 through October 2018.

API: `http://127.0.0.1:8000`; application: `http://localhost:3000`. The backend was restarted with `.env` explicitly loaded. Sessions created before restarts expired as expected for process-local storage.

## Final live HTTP results

| Workflow | Result | Actual MCP SQL calls | End-to-end latency |
|---|---|---:|---:|
| March 2018 late/on-time ratings | MEASURED_WITH_LIMITATIONS | 2 | 12.968 s |
| “Are delivery delays concentrated among sellers?” | MEASURED_WITH_LIMITATIONS; March inherited | 2 | 6.946 s |
| “What about February?” | MEASURED_WITH_LIMITATIONS; year and seller intent retained | 2 | 6.595 s |
| February–March revenue/profit divergence | EVIDENCE_RANKED_NOT_CAUSAL | 16 | 18.187 s |
| December 2016 seller concentration | MEASURED_WITH_LIMITATIONS; zero late orders, no seller query | 1 | 8.503 s |

All five responses are executable validated outcomes, not merely HTTP 200 clarifications. The session restored at revision 5. `live_http_journey.json` contains original questions, latency, full canonical records, actual SQL arguments/responses, database tool latency metadata, source references, validation evidence and execution traces.

Actual evidence changes execution: March has 1,496 late orders, so the seller partition executes. December 2016 has one timestamp-eligible order and zero late orders, so the coordinator stops after the delivery metric. March's unclassified deliveries also select the governed delivery-missingness follow-up. These values were retrieved live, not supplied by fixtures.

## Observed measurements and application verification

- March: 7,211 delivery orders; 7,003 timestamp-eligible; 1,496 late. Reviewed late orders average 2.27956 versus 4.22233 for reviewed on-time orders, a descriptive difference of -1.94277 rating points.
- Seller partition: 7,098 single-seller orders (6,913 eligible, 1,491 late), 90 multi-seller orders (90 eligible, five late), and 23 unknown mappings (none timestamp-eligible).
- The leading seller by late-order count has 38 late orders among 160 eligible single-seller orders: 23.75% late, accounting for 2.548625% of single-seller late orders. This is association, not responsibility.
- Finance evidence confirms revenue increased by 139,034.7300000040 while contribution profit decreased by 48,578.12892400006 in dataset-native units. The live adaptive finance result retains the accounting bridge, component ranking and per-order context.

A separate browser-submitted seller investigation completed in the real application. Business View visibly displayed the seller chart, 38/160, 23.75%, rounded 2.55% share, and all attribution buckets. Analyst selection was confirmed with the same 23.75% measurement. Six investigation POSTs were recorded: the five scripted turns plus this browser submission; changing views did not add an investigation POST.

The five actual HTTP records also passed ten production normalizer/component/PDF checks (Business and Analyst), with exact canonical record preservation. These are tests over real captures, not replacement data. Screenshot capture failed because of browser bridge/frame-limit errors; a visual PDF layout inspection and browser PDF download were not completed. Full Analyst evidence can overwhelm the automation accessibility tree; targeted DOM checks succeeded. No UI redesign was made.

## Integration fixes

- `mcp_server/runtime_tools.py`: recognize CTE references through SQLGlot lexical scopes while continuing to validate every underlying physical relation. Tests reject forbidden schemas, unqualified physical tables, out-of-scope aliases and write CTEs. No schema allowlist or permission expansion.
- `scripts/phase5_1_playground.py`: defer unused Gemini interpreter construction for pre-existing deterministic paths; preserve the complete mutable execution trace after adaptive follow-ups; use the bounded structured period proposal.
- `agent/delivery_review_routing.py`: accept only a singleton provider envelope before exact period matching; constrain Gemini period shape; prevent a new finance “Why…” question from reusing prior delivery findings.
- `agent/phase4c27a_interpreter.py`: optional provider response schema, used for bounded period interpretation. Date/intent validation still controls execution.
- `scripts/live_checkpoint.py`, `scripts/live_http_checkpoint.py`, `scripts/live_checkpoint_validate.py`, `frontend/tests/live-checkpoint-verify.mjs`, and the trace assertion in `scripts/p1_3_validate.py`: reproducible live diagnostics and regressions.

## Verification and retained failures

- 79/79 existing offline backend suites passed.
- 8/8 checkpoint guard/provider-envelope/topic-switch tests passed.
- 31/31 P1.1/P0.3 HTTP tests, 10/10 P1.2 tests, 10/10 seller tests passed.
- 66/66 frontend tests; TypeScript passed. Production build passed earlier in this checkpoint; subsequent changes were backend fixes and verification scripts, not frontend product code.
- 10/10 presentation checks over the final live HTTP records passed.

Earlier runs are retained separately: invalid credential, unavailable Docker engine, a real PostgreSQL statement timeout, unrecognized CTEs, Gemini shape/period clarifications, stale topic reuse and omitted follow-up traces. They are not counted as successful live outcomes. The final run required no raised database timeout, substituted model response, synthetic result, SQL permission bypass or evaluator weakening.

Key artifacts: `live_gemini_auth.json`, `live_http_journey.json`, `live_database_checkpoint.json` (earlier direct MCP scope, explicitly no Gemini), `live_month_inventory.json`, `live_frontend_verification.json`, and `live_*tests.log` / `live_regressions.log`. The runtime still has the previously documented bounded-capability, descriptive-only, process-local session and synchronous-provider cancellation limits. This checkpoint is not a production load or availability certification.
