# OpsLens backend release readiness

**Decision updated 5 November 2026: full release acceptance remains blocked.** Final Gemini and deterministic runs both pass 7/7 core cases, return all 19 responses, and pass 12/12 incident safety checks. The multidomain/provider-failure regression is resolved in the verified scope. The unchanged gate still fails on unsupported/unclassified incident coverage and insufficient recognized measured coverage. See [Final backend acceptance](FINAL_BACKEND_ACCEPTANCE.md) for final contracts, exact results and limitations.

## Final backend verification, 5 November

- Final deterministic run: `.runtime/benchmarks/20261105T043512Z/`; final restricted Gemini run: `.runtime/benchmarks/20261105T043542Z/`.
- **7/7 core, 19/19 HTTP 200 and 12/12 incident safety** in each mode; **4/4 independent refund/seller base-population reconciliations**. Gemini made 16 explanation calls: 15 returned, one 503; ten validated selections, five empty/invalid selections and one provider error safely fell back. Three refused/ambiguous cases skipped explanation.
- Gemini request latency: median **7.578 s**, maximum **12.055 s**; deterministic median **0.077 s**, maximum **11.662 s**. These are single-run observations, not service guarantees.
- **166 offline/fixture tests**, **50 established validator scripts plus five affected-adapter validators (77 assertions)**, **74 Node tests**, compilation, **83 live PostgreSQL/MCP/dashboard checks**, and **10 live session/replay checks** passed. Replay checks used Gemini-disabled real HTTP and PostgreSQL. Narrative inspection resolved **341/341 source references** and matched **49/49 values exactly** to their own live evidence.
- Separate database runs retain tiny preexisting finance floating-point differences (maximum observed **1.95e-9**); unchanged reconciliation tolerances pass. Narrative rendering never modifies a source value.
- Final gate: `PRE_UI_GATE_NOT_PASSED`, with `UNHANDLED_OR_UNEXPLAINED_INCIDENTS` and `INSUFFICIENT_LIVE_MEASURED_COVERAGE`. INC_008 remains unsupported; the frozen rubric recognizes one measured incident and classifies four later measured-with-limitations cases as other unverified. No incident mechanisms are certified.

The new backend explanation is additive, uses reviewed local sentences and clearly labelled hypotheses, and receives Gemini's validated template selection only. The outbound explanation contains static labels/references; the restricted live adapter adds only the fixed benchmark question. No database values, customer identifiers or documents are sent. Governed execution, exact evidence, session state and saved history remain authoritative. No frontend presentation changed.

The sections below retain the earlier provisioning and 4 November benchmark evidence for audit history. Their earlier provider failures are superseded by the final results above, not erased.

## PostgreSQL and MCP

Both a new disposable PostgreSQL 16 installation and the installed OpsLens database were exercised. The clean installation loaded 99,441 orders, 112,650 order items, 98,666 order-profitability rows and 360,129 GA4 sessions. The document index contained eight indexed chunks. The loader reads its explicit source manifest and keeps evaluator truth out of the runtime database. The rehearsal used a separate container, random credentials and a loopback port. It stopped its own container on completion.

The runtime verifies the login and read-only defaults when opening pooled connections. Generic SQL admits named relations, registered functions and approved cast types. It rejects indirect XML reads, unregistered functions, explicit custom operators, table sampling, locks, write statements, unknown relations and hidden-schema CTEs. Queries run under a read-only transaction with a row cap, statement timeout and catalog-only search path.

On the installed dedicated database, the grant migration retained the existing login and password. It removed the reader's old-view and automatic future-table grants, and removed public temporary-table and selected sensitive function privileges. The nine lookup indexes and staging statistics were applied. The pre-change grant extract is under `.runtime/pre-release-grants-20261104163104.sql`. These changes apply to PostgreSQL permissions and indexes; business rows and investigation history were preserved.

The live release check verifies the exact source inventory and actual SQL permission denials for staging reads and indirect SQL execution. It also exercises the governed SQL corpus under the real reader. There are 26 distinct archived statements. Four historical text/date comparisons are replayed through their corrected refund or finance component compiler. The original archived queries remain available for inspection. The corpus covers recorded queries and does not establish that every hypothetical query is safe.

## Independent numerical checks

The evaluator reconstructed finance amounts from staging profitability and its two adjustment tables in a read-only, repeatable-read transaction. It checked source uniqueness, post-join row counts, missing finance inputs, signed components and residuals. Separate SQL reconstructed purchase-month delivery and review populations from their source rows. Finance components were compared to the live MCP reader, and all six dashboard measures were compared to real HTTP responses. The files record input SHA-256 hashes, period bounds, counts, source totals and observed values.

|Measure|February 2018|March 2018|
|---|---:|---:|
|Placed orders|6,728|7,211|
|Financially represented orders|6,694|7,188|
|Effective revenue|844,178.71|983,213.44|
|Contribution profit|115,103.045692|66,524.916768|
|Contribution margin|13.634915%|6.766071%|
|Orders eligible for lateness|6,556|7,003|
|Late delivery rate|16.000610%|21.362273%|
|Reviewed orders|6,672|7,148|
|Mean order review score|3.827313|3.753567|

December 2019 and January 2020 had zero source orders. The dashboard returned unavailable readings for all six metrics. Count tolerances were zero, money tolerances were 0.02 for the dashboard and 0.05 for finance components, and rates and scores used 0.000001. The difference between placed and financially represented orders is material and is preserved in the evidence.

## HTTP and frontend contracts

The API now publishes the investigation envelope and success/error variants in OpenAPI. The fixture test sends real HTTP through the Next.js route handler to FastAPI with an isolated executor and temporary trace store. It verifies measured and partial results, exact decimals and large integers, unknown fields, cancellation, revision conflicts, storage limits, validation errors, service failures, replay, session reset and ownership-cookie forwarding. A separate outage fixture verifies liveness stays available while readiness returns HTTP 503. No frontend presentation code changed.

## First-release scope

Weekly relative periods, general AOV comparisons, comprehensive customer/product contribution rankings, and causal verification of incident mechanisms are excluded from the advertised scope. No additional analytical capability was added. The changes restore existing governed routes, period handling and evidence contracts.

## Verification ledger

|Verification type|Executed result|
|---|---|
|Clean Python API installation|The isolated environment installed `requirements-api.txt`, passed `pip check`, imported the MCP server and investigation runtime, and generated the API's OpenAPI schema.|
|Offline validators|All 50 scoped Phase 4–6 validation scripts passed. The Phase 5.3 core scoring fixtures passed 23/23 and incident scoring fixtures passed 113/113. These tests do not query business data.|
|Boundary and HTTP fixture tests|28/28 passed, including the real proxy transport, simulated database outage, registered SQL corpus and adversarial parser cases.|
|Frontend and syntax checks|74/74 Node tests passed. Python compilation succeeded.|
|Installed live PostgreSQL and HTTP dashboard|83/83 checks passed. Readiness returned HTTP 200. All 26 replayed query plans executed under the restricted reader. PostgreSQL denied direct staging and XML reads with SQLSTATE 42501.|
|Fresh database plus live dashboard|A separate initialization from repository inputs passed the same 83/83 checks, including the six dashboard metrics, finance components and empty periods.|
|Live API benchmark with Gemini disabled|All 19 requests reached FastAPI. The seven core cases passed, including causal refusal, both three-domain comparisons and exact-period evidence. All 12 incidents returned HTTP 200 and passed the existing safety checks.|
|Live API benchmark with Gemini enabled|Executed with the authorized outbound allowlist: 6/7 core cases passed; 11/12 incident responses passed structured safety checks, with one HTTP 503. Eight of 19 provider calls failed. Full release gate failed.|

The deterministic baseline is `.runtime/benchmarks/20261104T134423Z/result.json`; the adjacent `responses.json` retains redacted canonical evidence. The independent checks are `.runtime/release_checks_configured.json` and `.runtime/release_checks_disposable.json`. The reported data checks and benchmark were executed on 4 November 2026.

On 5 November, the scoped boundary/HTTP fixture suite passed again (28/28), as did all 74 Node tests, Python compilation, and offline outbound-allowlist checks across all 19 questions. The initial sandboxed fixture run stalled after 25 tests and was interrupted; the complete rerun outside the sandbox passed. These checks made no Gemini calls and do not erase the live failures below.

## Historical authorized Gemini verification, 4 November

The completed run is `.runtime/benchmarks/20261104T152422Z/result.json`, with adjacent `responses.json` and `provider_calls.jsonl`. It executed on 4 November 2026 UTC and was reviewed on 5 November. Readiness passed before external calls. All 19 fixed questions were attempted once through live HTTP; 16 cases reached Gemini and three were handled deterministically. The provider audit records 19 calls to `gemini-3.5-flash-lite`: 11 returned, six failed with code 504 and two with code 503. There were no policy-stop events. No extra questions or retries were introduced.

**Transmission scope:** the dedicated benchmark adapter reconstructs outbound content from the fixed question allowlist and reviewed static instructions/schemas. Explanation calls receive only approved explanation labels and field-reference names. It discards numerical database evidence, nested context, identifiers, raw rows and documents. The source manifest identifies Olist inputs as public anonymized data and augmentation inputs as synthetic; no database values were transmitted regardless of provenance. Credentials were used only for SDK authentication to Google's fixed HTTPS endpoint, never as prompt evidence or audit content. Database evaluation remained local and read-only; this benchmark changed no database permissions or production data.

This is a **restricted-input benchmark**, not a byte-identical test of the default application prompts. Replacing internal rewritten questions and removing dynamic context may affect results. The run establishes real provider participation under the authorized restrictions, not unrestricted model-path readiness.

|Measure|Deterministic baseline|Restricted Gemini run|
|---|---:|---:|
|Core case accuracy|7/7|6/7 (85.71%)|
|HTTP 200 responses|19/19|18/19|
|Incident structured safety|12/12|11/12; missing response unverified|
|Recognized measured incidents, frozen rubric|1|0|
|Independently verified incident mechanisms|0/12|0/12|
|Provider failures|Not applicable|8/19 calls|

End-to-end request latency was median **24.786 seconds**, maximum **56.746 seconds**, and minimum 0.004 seconds (deterministic handling). The full run took 424.112 seconds. The saved baseline has no per-request timings, so no latency improvement/regression percentage is claimed.

The failed core case, `multidomain`, returned `ACTIONABLE_EVIDENCE_GAP` with upstream `FINANCE_INVESTIGATION_NOT_EXECUTED`, despite its provider call returning successfully. This is a missing required answer, not a measured numerical mismatch. `shared_year` and the product/delivery cases passed their exact-period and numerical checks. Local independent staging reconciliation passed for the available INC_003, INC_004 and INC_010 aggregates. INC_012 returned HTTP 503 and has no Gemini-run numerical verification; its historical baseline result below must not be attributed to this run.

No unsupported causal certainty was flagged in the seven core or eleven structured incident responses. This is bounded structured-output evidence, not exhaustive proof of every claim or incident mechanism. The provider-failed INC_005, INC_006, INC_007, INC_009 and INC_011 returned `INTERPRETER_UNAVAILABLE`; INC_001 fell back to an evidence gap after a provider 503. The product explanation call timed out but its measured answer passed. INC_008 remained unsupported. No missing answer is counted as an accurate or safe completed investigation.

## Historical incident results and release blockers, 4 November

The deterministic baseline under the unchanged rubric counted **one measured descriptive incident, six actionable evidence gaps, one unsupported incident and four other unverified responses**. It verified **zero incident mechanisms**. Its gate returned `PRE_UI_GATE_NOT_PASSED` for three reasons:

1. **Provider-enabled acceptance failed.** Authorization is no longer the blocker. Resolve the multidomain regression and provider failure handling before claiming 7/7 core and 12/12 incident coverage. The restricted run had two actionable evidence gaps, one unsupported incident, eight other unverified results and one missing response. Its unchanged gate reported `CORE_LIVE_RUN_NOT_VERIFIED`, `CORE_REGRESSION_NOT_7_OF_7`, `INCIDENT_RESPONSE_COVERAGE_INCOMPLETE`, `SAFETY_REGRESSION`, `UNHANDLED_OR_UNEXPLAINED_INCIDENTS` and `INSUFFICIENT_LIVE_MEASURED_COVERAGE`. Here the safety failure reflects a missing response, not an observed unsafe claim. These labels do not negate the recorded provider calls.
2. **INC_008 remains unsupported for the full request.** It asks whether review deterioration was concentrated among late orders and particular sellers. The seller route supports delivery lateness; it lacks a governed seller-by-review attribution. The returned status was `NOT_YET_SUPPORTED`. Keep the limitation explicit in the UI and first-release scope. The frozen gate still counts this as unhandled.
3. **The historical rubric requires at least three measured incident cases and recognized one.** Four later refund and seller cases produced measurements with limitations that the rubric labels `OTHER_UNVERIFIED`. Separate staging SQL verified the base populations and values shown below. These checks do not verify the full explanations or change the acceptance score.

|Case|Independently reconciled reading|Remaining analytical limitation|
|---|---|---|
|INC_003|January 2018 had 398 refunded orders, 399 return events and 40,125.25 in refunds across 7,269 placed orders.|SKU and seller attribution of the spike is not established by those totals.|
|INC_004|August 2018 had 710 late orders among 6,351 orders eligible for lateness, from 6,512 placed orders.|The base reading alone does not certify an incident mechanism or every seller ranking.|
|INC_010|December 2017 had 287 refunded orders and 30,629.57 in refunds.|The supplier invoice and paid-media accrual questions remain unresolved.|
|INC_012|July 2018 had 203 refunded orders and 19,179.85 in refunds.|The totals do not resolve promotion exposure, order-value strata or causality.|

In the deterministic baseline, INC_001 returned reconciled accounting evidence. INC_002, INC_005, INC_006, INC_007, INC_009 and INC_011 returned evidence gaps. Security and stored-run checks should continue to display those dispositions separately from measured answers. Review the four supplemental results against the rubric before changing any future acceptance criteria.

See [the release runbook](RELEASE_RUNBOOK.md) for clean provisioning, verification commands, local evidence locations and benchmark modes.
