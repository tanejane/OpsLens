# OpsLens

OpsLens is an AI-assisted business investigation portfolio application: a Python/FastAPI backend, governed SQL and MCP tools, optional Gemini interpretation, and a Next.js/TypeScript interface. It reports descriptive evidence and scope limits, not proven business causes.

## Current application

- Overview and Explore show dashboard KPIs and comparisons for the selected periods.
- Investigations cover finance, delivery, products, customer satisfaction and supported concentration questions through governed routes.
- The unified workspace presents the direct answer, measured evidence, limitations and supported follow-ups. Agent execution is an optional collapsed diagnostic; it does not assert a globally verified chronology.
- Session context supports follow-up questions and reload recovery while the server session remains available. The browser stores an opaque session ID; an HttpOnly owner cookie controls access. Sessions are bounded, process-local and expiring, not enterprise user accounts.
- Saved evidence replay uses the local trace store and checks session ownership. Replay reads saved evidence without rerunning tools.
- PDF reports contain a readable answer-first summary and an exact `opslens-investigation.json` attachment with the full canonical record. Raw traces and document passages need not appear as printed pages.

Olist commerce and the separate GA4 demo environment represent different populations. Do not join them as the same customers. Evaluator ground truth must never enter runtime tools, prompts or retrieval.

## Local setup

Use Python 3.13 and Node.js 22 (validated locally with Node 22.14.0/npm 10.9.2). Database provisioning uses PostgreSQL 16 with pgvector; see the [release runbook](docs/audit/RELEASE_RUNBOOK.md).

From the repository root in PowerShell:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements-api.txt -r requirements-phase2b.txt -r requirements-phase2d.txt
python -m pip check
```

The API requirements install runtime packages, phase2b supplies ingestion dependencies, and phase2d includes pytest. These files use version ranges; they are not a locked Python environment. Tests have also been run in the existing local pytest 9.2.0 environment, which differs from phase2d's pytest 8 range. A clean installation still needs verification.

If `.env` does not exist, copy `.env.example` to `.env`. Merge the runtime reader settings from `.env.phase2d.example` and replace demonstration credentials locally. Do not overwrite an existing `.env`. Keep the privileged provisioning account separate from the MCP reader account.

Raw, processed and synthetic datasets are intentionally ignored by Git. A clone does not contain those large inputs. Obtain the datasets described in `docs/phase-history/2a.md` and the explicit input manifest in `scripts/load_phase2b_v3.py`; retain their provenance. Follow the release runbook to provision an empty database, load data, build the document index and grant the restricted reader role. Starting PostgreSQL alone does not initialize a usable OpsLens database.

Optional Gemini uses `GOOGLE_API_KEY` or `GEMINI_API_KEY` in the backend environment. Without a provider key, deterministic routes remain available. Never put provider keys in browser/public environment variables. Review external-data transmission before running live model benchmarks.

Start the API:

```powershell
python -m uvicorn api:app --host 127.0.0.1 --port 8000
```

In another terminal:

```powershell
cd frontend
npm ci
npm run dev
```

Open http://localhost:3000. Next proxies `/api/*` to `http://127.0.0.1:8000`; set server-side `OPSLENS_API_URL` only when changing that upstream. Configure `OPSLENS_FRONTEND_ORIGINS` for the exact browser origin. HTTPS deployments also require `OPSLENS_COOKIE_SECURE=1`. Development uses `.next-dev`; production builds use `.next`.

`GET /api/health` checks liveness; `GET /api/ready` checks the configured role and data dependencies. The CLI remains available as `python -m scripts.phase5_1_playground`.

## Validation

```powershell
python -m pytest -q scripts/test_audit_cohorts.py scripts/test_audit_sql_boundary.py scripts/test_release_sql_policy.py scripts/test_release_contract.py
python -m pytest -q scripts/test_backend_acceptance.py scripts/test_trace_projection.py scripts/test_replay_isolation.py
cd frontend
npm test
npx tsc --noEmit --incremental false
npm run build
```

Use `npm start` after a successful build. Additional live database reconciliation and optional model gates are documented in the release runbook. Windows environments that block asyncio socket-pair initialization cannot complete the async backend tests; do not interpret a hung run as passing.

## Repository guide

- `agent/`, `mcp_server/`, `retrieval/`: planning, routing, validation and governed evidence access. Phase-prefixed names can still be active dependencies.
- `frontend/`: app, components, report/PDF logic and regression fixtures.
- `config/`, `db/`, `sql/`: metric contracts, initialization and reconciliation.
- `scripts/`: provisioning, acceptance/regression tests and reproducible evaluations.
- `data/documents/`, `data/eval_ground_truth/`: document fixtures and evaluator-only labels.
- `reports/`, `docs/`: retained evidence, contracts and phase history. Historical reports describe their recorded run, not certification of the current checkout.
- `.runtime/`: ignored local traces and diagnostics; `.env`, environments, databases and build outputs must stay out of Git.

See [cleanup and test follow-up](docs/audit/FRONTEND_CLEANUP_FOLLOWUP.md) for the current validation results and remaining limitations. This portfolio project is not production-certified.
