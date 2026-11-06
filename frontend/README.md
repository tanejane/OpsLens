# OpsLens frontend (Phase 1)

## Local run

From the repository root, start the existing PostgreSQL service and initialize the existing Python environment:

```powershell
docker compose up -d postgres
python -m pip install -r requirements-api.txt
```

Set `GOOGLE_API_KEY` (or `GEMINI_API_KEY`) in the backend process environment to enable the existing Gemini interpretation path. Without a key, the API keeps Gemini interpretation disabled and the existing deterministic routes remain available. The API does not receive SQL from the browser; it routes each question through the existing Phase 5.1/5.2E/5.3C runtime and governed MCP tools.

Start the API in one terminal:

```powershell
python -m uvicorn api:app --reload --host 127.0.0.1 --port 8000
```

Install and start the separate Next.js app in another terminal:

```powershell
cd frontend
npm install
npm run dev
```

Open <http://localhost:3000>. Next.js proxies `/api/*` to the local API on port 8000. Keep provider keys in the backend environment only. If your database is not initialized, use the repository's established data-load/setup instructions before running a live investigation. The saved evaluation overview can still be read from the repository report files when PostgreSQL is unavailable.

## Scope

The first phase implements the overview, investigation workspace, and activity/evaluation summary. Metrics and evidence navigation explain the current scope and are not presented as implemented data browsers. Saved scenario rows are explicitly labeled as evaluation report scenarios, not recent live activity. Evaluation data comes from `reports/phase5_3f_pre_ui_review.json`; the API reports acceptance status from that source without changing the gate.

Investigation results remain in the current browser session only. Persistent history is intentionally not enabled because the application has no authenticated user identity, workspace isolation contract, retention policy, or deletion controls. A future history feature must define those boundaries before saving questions or results to browser or server storage.
