# Phase 4C.26 — Bounded clarification recovery

Merge the `agent/`, `scripts/`, `docs/` directories into the existing repository. Keep all previous modules. No database migration, grant, allowlist or metric changes.

Run `python -m scripts.phase4c26_validate` and the existing 4C.25, 4C.24B regression suites. For live integration, launch `python -m scripts.phase4c26_unified_playground`.

Test sequences independently (restart playground for each, or use `cancel`):

1. `How were sales in June 2018?` → `no, I meant May 2018` → `item GMV` → `health and beauty`.
2. `sales` → `financial revenue` → `2018年六月`.
3. `sales for June 2018` → `units` → `no, item GMV` → `beleza_saude`.
4. `sales for June 2018` → `What is the late delivery rate in June 2018?`.

This phase only recovers explicitly stated month-year corrections/replies and selected finance/item metrics. It deliberately does not infer relative years, arbitrary multilingual sentences, new category aliases, causal claims, inventory, or stockouts. It does not edit past answers after execution; a fresh explicit query is required. As with 4C.25, the clarified question dispatched downstream is a composed query; caller audit metadata for the original multi-turn utterances is not yet implemented.
