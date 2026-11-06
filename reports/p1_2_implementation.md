# P1.2 evidence-driven adaptive investigation

The runtime now retains request-local execution state and evaluates validated evidence before requesting additional governed analyses. Existing finance premise/component/intensity planning remains in place. No orchestration dependency, SQL permission or calculation definition was added.

## Changes

- `agent/investigation_state.py`: bounded state, action deduplication, request-local successful-query reuse, tool accounting, deadline checks and trace snapshots. Defaults: four coordinator stages, 40 MCP calls, 120 seconds. The initial existing coordinator counts as one stage; its own bounded internal steps remain separately reported in `adaptive.trace`.
- `agent/evidence_followup.py`: a closed registry of delivery-missingness and review-population-coverage analyses using existing compilers and validators. Evidence selects candidates; each completed step triggers reassessment. Supporting delivery populations must reconcile to the initial cohort. Review-source population evidence remains explicitly separate and never replaces the delivery denominator.
- `scripts/phase5_1_playground.py`: shared budgets around initial and supporting execution, including graph/finance MCP readers; canonical evidence archive, execution trace and error retention preserved.
- `agent/phase4c7_adaptive.py`: component, evaluation and intensity failures retain previously validated finance findings rather than discarding the completed stages.
- `frontend/components/delivery-review-comparison.tsx`: combines completed follow-up conclusions with the original Business findings; Analyst adds supporting evidence and an optional step trace. No internal action/status labels enter the primary Business explanation.
- `scripts/p1_2_validate.py`: evidence-dependent branching, safe partial results, budgets, duplicate prevention, contradictions, finance recovery and real HTTP session isolation/follow-up tests.
- `scripts/p1_1_validate.py`: external mock now supplies valid delivery/review responses for newly selected governed calls; the HTTP journey asserts six calls across two three-step investigations.
- `frontend/tests/comparison.test.mjs`, `frontend/tests/normalize.test.mjs`, `frontend/tests/fixtures/p1_2_adaptive.json`: rendered-view and PDF/canonical preservation checks using captured offline coordinator responses.

## Example traces

1. Complete late/on-time cohorts and no missing review-view rows: initial comparison → QUESTION_ADDRESSED. No follow-up query.
2. Unclassified deliveries plus absent review-view rows: initial comparison → delivery missingness validated → broader review population validated → QUESTION_ADDRESSED. Three MCP calls in the HTTP test.
3. Same initial evidence, later review service failure: initial comparison → delivery missingness validated → review check failed → preserve initial comparison and delivery proof; stop FOLLOWUP_UNAVAILABLE_OR_CONTRADICTORY.

Changing only the unclassified count to zero removes the delivery action while retaining the review action. Changing both triggers to zero removes both. No reporting month is hardcoded in production selection. Tests use July 2019, September/October 2020 and inherited finance fixtures.

`reports/p1_2_example_traces.json` records these offline coordinator examples. Its tool counts cover follow-up calls only because initial evidence is supplied as a previously validated fixture. Actual HTTP tests execute the initial compiler as well.

## Verification

- Existing backend matrix: 79/79 suites passed; `reports/p1_2_regressions.log` and `reports/p0_3_offline_validation.json`.
- P1.1/P0.3 HTTP regression run: 31/31 tests passed; `reports/p1_2_http.log`.
- P1.2 acceptance tests: 10/10 passed, including actual HTTP evidence-dependent branching and session isolation; `reports/p1_2_targeted.log`.
- Frontend: 64/64 passed, including both rendered workspaces and both PDF modes; `reports/p1_2_frontend.log`.
- TypeScript and production build passed; `reports/p1_2_typescript.log`, `reports/p1_2_build.log`.
- Local PostgreSQL connection refused (10061); no live SQL/MCP/Gemini success is claimed. `reports/p1_2_live_diagnostic.json`.

## Boundaries

The extension registry is deliberately narrow: delivery/review coverage investigation plus the existing finance adaptive planner. Other registered metric and graph routes retain their original behavior and stop when no relevant extension is registered. Selection is deterministic and evidence-driven; Gemini continues contextual interpretation and the existing finance planning role, but does not author tool SQL or invent actions.

Missing reviews within otherwise present review-view rows do not trigger redundant coverage queries: the initial comparison already reports those denominators. A separate review-population query runs only for absent review-view rows. Additional results can qualify applicability; they cannot identify why customers rated an order or establish causation.

Deadlines bound asynchronous waits and are checked before/after tool execution. Existing synchronous Gemini SDK calls cannot be forcibly interrupted mid-call; an overrun is detected when control returns. A canceled database operation also remains subject to existing MCP statement/connection timeouts. Session persistence retains P0.3's single-process deployment boundary.

Verification is offline with mocked external data/model boundaries, rendered component tests and PDF content/evidence tests. No interactive browser journey, PDF visual QA or live data certification is claimed.
