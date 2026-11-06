# Phase 4C.16 — bounded natural-language delivery metrics

Install by merging the `agent/`, `scripts/`, `docs/` directories into the existing OpsLens repository. Requires working 4C.13 and 4C.15 modules, validated PostgreSQL view and MCP reader. Does not change any database policy.

Test: `python -m scripts.phase4c16_validate`
Live: `python -m scripts.phase4c16_unified_playground`

Try in order:
1. What percentage of orders were delivered late in June 2018?
2. How long did deliveries take in May 2018?
3. What about June 2018?
4. And the late delivery rate?
5. Did late delivery improve from May 2018 to June 2018? (NOT_YET_SUPPORTED)
6. What was our average customer satisfaction score in June 2018?
7. What was our effective revenue in April 2018?
8. Which five sellers received the most unique orders in June 2018?

**Boundaries**: conservative deterministic delivery lexical grounding (not general Gemini delivery interpretation); one purchase month per metric; no delivery comparison or cross-domain causal diagnosis; contextual follow-ups require delivery as the active successful route; missing periods clarified; finance/graph/CX delegated unchanged. All SQL comes only from Phase 4C.15 audited compiler; live MCP access must pass existing checks. Invalid or blocked requests cannot modify active context.
