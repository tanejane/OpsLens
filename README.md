# OpsLens — Project guide

OpsLens is a governed business investigation agent over the Olist commerce world and a separate GA4 demo environment. **Do not join these populations as the same customers.**

## Where to start

- **Local API:** install `requirements-api.txt` and run `python -m uvicorn api:app` against a provisioned database.
- **Unified investigation CLI:** `python -m scripts.phase5_1_playground`.
- **Audit and readiness decision:** see `docs/audit/FRONTEND_READINESS.md`.
- **Backend release verification:** see `docs/audit/RELEASE_READINESS.md` and `docs/audit/RELEASE_RUNBOOK.md`.
- **Earlier semantic query playground:** `python -m agent.phase4b1_semantic_playground`
- **Offline semantic query tests:** `python scripts/phase4b1_validate_semantic_queries.py`
- **Text-date regression tests:** `python scripts/phase4b1_validate_date_casts.py`
- **Live diagnostics:** `python scripts/phase4b1_diagnose_query.py "How many orders were placed in June 2018?"`
- **Earlier investigation playground:** `python -m agent.phase4b_investigation_playground`
- **MCP server:** `mcp_server/server.py` / `mcp_server/runtime_tools.py`
- **Metric definitions:** `config/metric_catalog.json`
- **Database setup:** `db/init/`, `db/migrations/`, `docker-compose.yml`

## Organization

- `agent/`: Python modules. Names beginning with `phase` identify when they were introduced, not whether they are obsolete.
- `scripts/`: validation, data preparation, controlled fixture generation, and smoketests.
- `retrieval/`: hybrid document retrieval.
- `data/raw`, `data/processed`, `data/synthetic`: keep as inputs / reproducible data layers.
- `data/eval_ground_truth`: **evaluator-only**; never expose to agent tools, prompts, MCP runtime, or RAG.
- `docs/`: dataset audits and assumptions; `docs/phase-history/`: historical phase READMEs (not runtime dependencies).
- `config/`: governed metrics and settings.

## Important limitations

Phase 4B.1 is a single-relation query preview; it is **not** a generalized metric/join engine yet. Do not interpret `AVG(gross_profit)` as margin or treat a successful SQL execution as evidence of correct business semantics.

