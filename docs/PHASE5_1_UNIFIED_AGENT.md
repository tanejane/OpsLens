# Phase 5.1: bounded unified OpsLens entry point

## Scope
Adds `agent.phase5_1_unified.UnifiedSession`, one CLI entry point, and independent, offline contract tests. Reuses the already-tested Phase 4C.26 RecoverySession, the 4C.24 language layer, product/review/delivery/finance domain routing, MCP readers, and graph planning. Nothing modifies SQL, tables, grants, MCP allowlists, financial definitions or investigation policies.

**Gemini is opt-in.** `python -m scripts.phase5_1_playground` runs the established deterministic path; `python -m scripts.phase5_1_playground --gemini` uses the optional Gemini intent adapter for fresh questions. Existing clarification follow-ups bypass Gemini to preserve conversation state. `GOOGLE_API_KEY` or `GEMINI_API_KEY` must be configured to use the API. Gemini requests incur API usage.

## Safety architecture
1. Phase 4C.27A validates the Gemini output schema and identifiers, but that is not authorization.
2. Independent 5.1 bridge verifies the original user utterance independently contains the proposed month/year, metric and category, and only accepts registered metric/domain combinations.
3. The bridge builds a *fixed canonical question*, never SQL; the established routed executors still enforce all query constraints and MCP policy.
4. Explicit investigations delegate the **original input** to existing investigation routing, never a model-synthesized causal claim.
5. Vague requests use the existing clarification session; invalid/unverifiable interpretation fails closed, rather than silently executing.

This is deliberately a **narrow first integration**, not universal English understanding. Some reasonable English paraphrases will ask for clarification if their metric or period is not independently corroborated. Independent confirmation is lexical and not a full semantic parser. Do not claim that a successful structured model response certifies correct business intent. Gemini may be unavailable and is not automatically assumed faster; measure latency and cost before adopting default-on.

## Validation
```
python -m scripts.phase5_1_validate
python -m scripts.phase4c27a_validate
python -m scripts.phase4c26_validate
python -m scripts.phase4c24b_validate
```

Live smoke test, without Gemini:
```
python -m scripts.phase5_1_playground
```
Live smoke test, with opt-in Gemini interpretation:
```
python -m scripts.phase5_1_playground --gemini
```
Suggested live inputs: `how much beuty item GMV in Jun 2018?`, `What is the late delivry rate in June 2018?`, `How were sales in June 2018?` then `item GMV` then `health and beauty`, and `Why did revenue go up but profit go down in March 2018?`. Check that the latter follows your existing investigation guardrails, not fabricated findings.

## Remaining gates
- Live smoke test of integrated Gemini path and deterministic-only path; independent reconciliation already covers the previously tested June category and delivery values, not arbitrary intent combinations.
- Evaluate false routes, unsupported categories, ambiguous requests, prompt injection, latency and model costs across a larger corpus.
- Broader multi-domain orchestration, hypothesis validation, approval workflows, traces and user interface remain Phase 5.2 onwards.
