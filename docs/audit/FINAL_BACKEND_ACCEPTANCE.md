# Final backend acceptance

5 November 2026. **Backend reliability has improved; full release acceptance remains blocked.** The core analytical path remains governed and deterministic. Gemini is optional presentation and interpretation assistance, never an evidence authority, SQL author or permission provider. No frontend presentation, datasets, database permissions or business records were changed.

## Implemented behavior

- The API runtime tries existing deterministic routes first. It commits successful recovery state into the existing session-owned object, preserving follow-up and replay behavior. Failed speculative parsing uses a copy and cannot replace session state.
- Trusted internal finance subquestions use `CompiledComparisonInterpreter` in both modes, followed by the same period grounding, governed SQL and evidence validators. Refund, seller and delivery/review routes no longer ask a model to reconfirm periods already resolved by deterministic context validation. The known multidomain dependency is removed without altering its metrics or numerical assertions.
- Existing scalar/ranking interpretation remains available when deterministic parsing cannot resolve the request. Provider or invalid-output fallback uses the original question and model-disabled recovery, not model-proposed SQL or unverified dates. Diagnostic evidence gaps do not trigger unnecessary interpretation.
- Explanation runs after initial evidence, bounded follow-up and document corroboration. It cannot convert successfully validated evidence into HTTP 503. Partial evidence and retained completed steps remain distinct from a completed investigation. Earlier proofs retained after a failure are labelled `retained_fact` with `completed_step_only_not_complete_investigation` scope.
- Natural-language sentences are rendered from reviewed templates with exact local values, periods, units and population records. Finance and review denominators stay separate. Accounting contributions are explicitly noncausal. Hypotheses use the reviewed general-business templates, include missing evidence and supporting/weakening checks, and remain `UNVERIFIED_HYPOTHESIS`.
- Gemini selects an allowed presentation/template ID with the exact required reference set. It may prioritize a hypothesis within the hypothesis section, but cannot move speculation ahead of facts or remove contrary evidence and limitations. Extra prose, fabricated figures, unknown IDs, malformed references and invalid JSON are rejected. The deterministic explanation remains available.
- The SDK uses a fixed Google HTTPS endpoint, a 12-second timeout, one attempt (zero automatic retries), and no redirects or ambient proxy. The asynchronous explanation has a 15-second ceiling. Provider errors retain sanitized type/code/latency metadata. These are per-call limits; existing investigation budgets still bound analytical steps and tools. Optional explanation adds up to 15 seconds after analytical work.

This is constrained Gemini-assisted explanation, **not unrestricted model-authored prose or novel causal discovery**. This design deliberately provides a verifiable statement set instead of relying on a second model to judge hallucinations. Readability is improved through backend sentences, grouping and emphasis; no user study or frontend rendering acceptance is claimed.

## Data-sharing boundary

The new explanation request contains only `available_explanations`: reviewed static codes and field-reference labels. No question, measurements, periods, populations, identifiers, raw rows, prior history or documents are included by the application explanation path. Exact business values are inserted locally after validation.

Live verification uses the existing dedicated restricted benchmark adapter. It adds only the corresponding one of the 19 fixed authorized questions, validates reviewed instruction hashes and allowed labels/references, and stops on an unknown transmission. The Olist source manifest identifies public anonymized inputs and synthetic augmentation; nevertheless, no database values are transmitted. API credentials are authentication only, never prompt evidence. The benchmark does not authorize other questions or arbitrary production evidence. Existing legacy intent routes are not a blanket authorization for additional external transmission.

## Frontend-ready response contract

The envelope stays `opslens.investigation.v1`. Existing `result`, `canonical_result.payload`, status, evidence, source scope, uncertainty, session revision and error semantics remain authoritative. The additive `payload.explanation` has:

|Field|Contract|
|---|---|
|`version`|`opslens.explanation.v1`|
|`status`|`MODEL_SELECTED`, `DETERMINISTIC`, or `DETERMINISTIC_FALLBACK`; not an evidence-verification status|
|`sections[].kind`|`fact`, `retained_fact`, `finding`, `accounting_contribution`, `hypothesis`, or `limitation`|
|`sections[].text`|Reviewed local template with exact source values; no unvalidated model prose|
|`sections[].evidence_refs`|JSON pointers into the original payload for evidence-backed statements; empty for general hypotheses|
|Value and scope fields|Exact values, source, unit, period/population where applicable; nested executor evidence remains the source of truth|
|Hypothesis fields|`UNVERIFIED_HYPOTHESIS`, general-knowledge basis, missing evidence and next check; no probability or causal certification|
|`selection`|Validated model selection or null; its static template references are selection labels, not evidence JSON pointers|
|`fallback_reason`, `error_type`, `provider_code`, `provider_elapsed_ms`|Optional presentation diagnostics; never display fallback as failed governed evidence|
|`causal_claim`|Always false in this presentation contract|

Large integers and Decimals retain the existing canonical exact-string encoding. Replay returns the stored explanation and evidence without another model or tool call. Unknown fields remain losslessly retained. A rendering failure returns an empty explanation with `RENDERING_UNAVAILABLE` while preserving the original result. Consumers must still present the original limitation/error status, including unsupported and ambiguous requests; explanation availability is not a reason to mark them measured.

## Validation ledger

|Verification|Executed result|
|---|---|
|Offline/backend HTTP fixtures|**166 passed**, zero failures; includes provider success, 503/504, timeout, invalid/fabricated output, missing/partial/unsafe/ambiguous requests, precision, mixed populations, session identity and replay. `.runtime/final_backend_pytest.txt`.|
|Established offline validator scripts|**50/50 passed**. Two initial failures were Windows stdout encoding and passed under UTF-8; one old static wiring assertion was updated for the intentionally compiled internal finance path. `.runtime/final_backend_validators.json`.|
|Additional affected adapter validators|**5/5 scripts, 77/77 assertions passed**: Gemini schema, semantic grounding, finance NL, finance reliability and graph planner. `.runtime/final_backend_adapter_validators.json`.|
|Frontend regression tests|**74/74 passed**; no presentation code changed.|
|Python compilation|Passed for changed runtime, provider, explanation, benchmark and test modules.|
|Live configured PostgreSQL/MCP/dashboard|**83/83 passed**, including independent finance/operational reconciliation and all 26 archived governed SQL replays. `.runtime/release_checks_configured.json`, 2026-11-05T04:29:15Z. Clean provisioning was previously verified; it was not repeated in this task.|
|Live session persistence/replay, Gemini disabled|**10/10 checks passed**: two fixed benchmark questions through session HTTP, exact saved canonical results including explanations, zero replay external calls, revision advance and reset. `.runtime/final_backend_live_replay.json`.|
|Canonical JSON Schema|**19/19 final live Gemini records passed** the published additive explanation schema.|
|Narrative fidelity on final live Gemini records|**341/341 evidence pointers resolved; 49/49 rendered numeric values exactly matched their own source evidence.** `.runtime/final_backend_fidelity.json`.|

|Fixed 19-case live benchmark|Deterministic|Gemini enabled, restricted input|
|---|---:|---:|
|Core score|7/7|7/7|
|HTTP 200 responses|19/19|19/19|
|Incident structured safety|12/12|12/12|
|Independent concentration checks|4/4|4/4|
|Recognized measured incidents under frozen rubric|1|1|
|Mechanisms independently certified|0/12|0/12|
|Median request latency|0.077 seconds|7.578 seconds|
|Maximum request latency|11.662 seconds|12.055 seconds|
|Whole-run wall time|29.069 seconds|133.108 seconds|

Final artifacts: `.runtime/benchmarks/20261105T043512Z/` (deterministic) and `.runtime/benchmarks/20261105T043542Z/` (Gemini), each containing `result.json` and `responses.json`; the latter also contains `provider_calls.jsonl`. Aggregate results and source SHA-256 hashes are in `.runtime/final_backend_acceptance.json`.

The final Gemini run made **16 explanation calls**, with **15 returned and one provider 503**. Ten selections passed validation, five returned an empty/declined or invalid selection and fell back, and one provider error fell back. Three refused/ambiguous cases made no explanation call. There were no policy-stop events, retries or model-driven evidence executions in this run. No unsupported model prose entered a response: only exact validated codes/references were accepted. Bounded incident safety checks found no causal-certainty violation, but are not proof of every possible future response.

Compared with the historical 7/7 deterministic baseline, core accuracy is preserved. Compared with the earlier restricted Gemini 6/7 run, the multidomain regression and missing incident response are resolved. A preliminary run of this implementation also scored 7/7, with five provider errors safely absorbed; the final run was repeated after session-identity and narrative-projection fixes. Provider availability varies; no population-level accuracy or latency guarantee is inferred.

Across separate deterministic/Gemini database executions, 158 nested finance numeric leaves differed in low-order floating-point digits (maximum absolute difference **1.95e-9**), with no nonnumeric differences in compared evidence fields. Existing numerical tolerances passed unchanged. These differences arise before narrative rendering; exact within-run narrative fidelity passed. Migrating source financial floating-point columns is separate precision work and was not performed.

Both final benchmark processes intentionally exit nonzero because the release gate remains **PRE_UI_GATE_NOT_PASSED**. The final Gemini blocking reasons are exactly **UNHANDLED_OR_UNEXPLAINED_INCIDENTS** and **INSUFFICIENT_LIVE_MEASURED_COVERAGE**. The deterministic run additionally cannot satisfy the live-Gemini requirement. Coverage is one measured descriptive case, six actionable gaps, one unsupported case and four other unverified responses. The acceptance rubric was not changed.

An initial live attempt was interrupted while Docker/PostgreSQL was down; it is incomplete evidence under `.runtime/benchmarks/20261105T042354Z/`, not a passing run. Starting the existing engine restored service without permission or business-data changes. Offline fixtures do not substitute for any of the live results above.

## Remaining analytical and release limitations

The acceptance rubric is unchanged. Seller-by-review attribution for INC_008 remains unsupported. The frozen incident rubric does not classify later refund/seller `MEASURED_WITH_LIMITATIONS` results as measured descriptive cases; supplemental source reconciliation does not change that score. No incident mechanism is independently certified. Closing these gates requires explicit scope/criteria review or separately governed capability work, not relabelling evidence gaps or weakening tests.

Supplier invoice linkage, item-level profit/cost allocation, campaign incrementality, independently measured stockout lost demand, and causal identification remain unavailable or unverified. Recorded refunds use purchase cohorts and synthetic events, not cash-flow periods or SKU allocations. Delivery/review association does not identify responsibility or causation. Effective financial and operational layers contain modeled values. GA4/Olist cross-environment linkage remains unapproved.

The external provider still experiences failures; deterministic availability is tested, not a provider SLA. Hypothesis templates are bounded general knowledge and cannot discover new mechanisms. The limited fixed benchmark does not establish accuracy across every phrasing, period, population, concurrent load or deployment environment. No full production-readiness claim is made.

## Affected implementation and reproduction

- `scripts/phase5_1_playground.py`: evidence-first runtime, trusted period routing, session-state preservation, post-evidence explanation.
- `agent/phase5_1_unified.py`: original-input deterministic fallback and failure diagnostics.
- `agent/phase5_1_explanation.py`: explicit outbound projection, strict selection validation, exact local narrative and mixed-evidence handling.
- `agent/provider_policy.py`, `phase4c27a_interpreter.py`, and existing router/finance/semantic/investigation adapters: bounded SDK options.
- `config/investigation_result.schema.json`: additive explanation documentation/shape; no version break.
- `scripts/restricted_gemini_benchmark.py`: reviewed static explanation references and matching bounded provider timeout; same 19 questions.
- `scripts/test_backend_acceptance.py`: fidelity, mixed evidence, unsupported/unsafe/ambiguous inputs, provider failures, internal routing, session identity and replay. Existing `phase5_1_validate.py` fallback assertions and `phase5_2e_validate.py` wiring assertion now reflect intentional deterministic behavior; numerical, SQL and benchmark criteria were not relaxed.

Run `python -m pytest -q scripts/test_backend_acceptance.py` for the focused offline suite. The complete fixture suite is the existing audit/release tests plus `p0_1_validate.py`, `p0_3_validate.py`, `p1_1_validate.py` through `p1_3_validate.py`, and `p2_1_validate.py` through `p2_3_validate.py`. Run `python -m scripts.release_checks` for read-only live source checks and `python -m scripts.release_benchmark` for the fixed deterministic HTTP benchmark. Authorized `--gemini` mode uses the restricted adapter. A nonzero benchmark exit is expected while acceptance gates remain open; it is not permission to change the criteria.
