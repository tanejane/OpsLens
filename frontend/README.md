# OpsLens frontend

Next.js/TypeScript interface for the governed OpsLens API. See the root [README](../README.md) for Python/database provisioning, environment settings and limitations.

```powershell
npm ci
npm run dev
```

Open http://localhost:3000 with the API running at http://127.0.0.1:8000. The Next API proxy uses server-side `OPSLENS_API_URL` when configured. Provider credentials belong only in the backend environment.

The unified workspace provides Overview, Explore, Investigations and Reports. Direct answers retain evidence, population limits and causal restrictions. Collapsed Agent execution diagnostics and owned-session replay remain available. Reload restores a live server session via an opaque browser session ID and an HttpOnly owner cookie; server restarts/expiry require a new investigation. This is not enterprise authentication or permanent browser history.

PDFs summarize the answer and measurements, with the exact canonical record embedded as `opslens-investigation.json`. Legacy Business/Analyst adapters remain covered by tests, but the application has no global mode toggle.

```powershell
npm test
npx tsc --noEmit --incremental false
npm run build
npm start
```

Development output uses `.next-dev`; builds use `.next`. Commit `package-lock.json` and use `npm ci` for reproducible frontend installs. Do not commit build output, local environment files or incremental TypeScript metadata.
