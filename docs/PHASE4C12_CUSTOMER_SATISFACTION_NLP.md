# Phase 4C.12 — Customer satisfaction NL integration

## Scope
Adds a bounded natural-language recognition/grounding path over the existing Phase 4C.11 MCP-verified satisfaction executor. It does **not** retrain a model or create an autonomous cross-domain investigator. Existing Gemini finance/graph/investigation routing is preserved. Satisfaction routing uses deterministic, explicitly scoped vocabulary and requires a named purchase month/year, with two strictly scoped follow-up forms. SQL is always compiled by `agent.phase4c11_satisfaction` and evaluated under the existing MCP reader.

## Installation
Merge only `agent/phase4c12_cx_nlp.py`, `scripts/phase4c12_unified_playground.py`, `scripts/phase4c12_validate.py`, and this document into the existing OpsLens project. Phase 4C.8 and 4C.11/4C.11B code and the audited `semantic.order_review_evidence_v1` view must already be present. No DB migration, permissions, or allowlist changes.

## Tests
```
python -m scripts.phase4c12_validate
python -m scripts.phase4c12_unified_playground
```

Try these in sequence:
1. `What was our average customer satisfaction score in June 2018?` (4.25362318840579710145 from last verified dataset)
2. `What about May 2018?` (same metric, new purchase month)
3. `And the bad review rate?` (same May period, low_rating_rate)
4. `Did satisfaction drop from May to June 2018?` (NOT_YET_SUPPORTED; no comparison queries)
5. `How many customers left reviews in June 2018?` (NEEDS_CLARIFICATION: unique customers vs reviewed orders)
6. `Which five sellers received the most unique orders in June 2018?` (existing GraphPlanner)
7. `What was our effective revenue in April 2018?` (existing finance interpreter)
8. `What about May 2018?` (finance follow-up, **not** CX, because active domain switched)

## Safety boundaries
- One month only; no unsupported comparisons, rankings or investigations are executed through the satisfaction executor.
- Ambiguous customer-versus-order grain requests are blocked.
- Context is updated only after a successfully validated measurement. Invalid/failed turns preserve previously successful state.
- There is **no LLM-based free-form satisfaction metric interpreter** in this increment. New paraphrases beyond listed patterns may require expansion and tests; unsupported requests are not silently mapped.
- Existing financial and graph routes continue through the prior Phase 4C.8 dispatcher unchanged.
- Existing MCP permissions and measurement validation remain mandatory; no implicit approval or causal claims.
