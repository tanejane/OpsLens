# Investigation origin rejection

## Root cause

The reported browser URL is `http://192.168.100.20:3000`. The previous API default trusted `http://localhost:3000`; no frontend-origin setting was present in the local `.env`. These are different browser origins. Next correctly forwarded the browser's Origin and Fetch Metadata, so FastAPI rejected the session/investigation mutation. This was a local origin-configuration mismatch, not an analytical or database failure. The screenshot does not prove the original Sec-Fetch-Site value; cross-site remains an independent rejection condition.

The previous API also installed CORS before explicitly loading local environment configuration and implicitly accepted its Host-derived base URL for mutations. Those paths are now replaced by one startup configuration shared by CORS and the CSRF middleware.

## Configuration applied locally

The repository-root `.env` now contains:

```dotenv
OPSLENS_FRONTEND_ORIGINS=http://localhost:3000,http://192.168.100.20:3000
```

Restart FastAPI to load it. Restart Next after updating its proxy code (rebuild first when using `next start`). If a shell already sets `OPSLENS_FRONTEND_ORIGINS`, that process environment takes precedence over `.env`; remove the stale shell value or set it to the same explicit list. The plural variable takes precedence over legacy `OPSLENS_FRONTEND_ORIGIN`. Without either variable, the existing localhost:3000 default remains. Origins require scheme, host and port without a path or trailing slash. Add `http://127.0.0.1:3000` only if that exact browser address is also intended. A changed LAN address must be deliberately configured.

`OPSLENS_API_URL` is the server-side upstream address, normally `http://127.0.0.1:8000`; it does not define the trusted browser origin. Browser requests should use the existing same-origin `/api` proxy. For HTTPS deployment set `OPSLENS_COOKIE_SECURE=1`; this flag is not forced for the user's HTTP local-development URL.

## Changes and preserved boundaries

- `frontend_origins.py`: parse an explicit comma-separated origin list; reject empty entries, wildcard origins, credentials, paths, query strings, fragments and invalid ports.
- `api.py`: load root `.env` without overriding process environment before configuring CORS and CSRF; remove implicit Host-derived trust. Reject present but empty/null/unconfigured Origin and cross-site mutation requests. Existing non-browser requests without Origin remain supported; session ownership is still required independently.
- `frontend/app/api/[...path]/route.ts`: preserve Origin, Sec-Fetch-Site and cookie values; also preserve present empty headers so an invalid empty Origin cannot become an absent Origin. No Origin rewriting or wildcard trust.
- `.env.example`: document the origin list and secure-cookie deployment setting.
- `scripts/test_frontend_origins.py`: configuration and API boundary regression tests.
- `scripts/test_release_contract.py` / `frontend/tests/release-proxy.mjs`: run the existing contract checks over HTTP through a real production Next server and real FastAPI with isolated executor fixtures and trace storage.

Session credentials remain HttpOnly, SameSite=Strict and scoped to `/api`. HTTPS/explicit Secure flags, owner verification, revision checks, saved replay and CSRF rejection are retained. No analytical logic or frontend design changed.

## Verification

- Production Next build passed, including lint and TypeScript checks.
- Frontend suite: **81 passed, 0 failed**.
- Origin and backend acceptance pytest suites: **35 passed**.
- Existing session and trace/replay regressions: **29 passed**. Final origin-only rerun, including cross-site requests with no Origin: **12 passed**.
- Real Next/FastAPI contract suite: **3 passed**. Both configured origins accepted. Seven hostile/header configurations across POST session, POST investigation and DELETE session produced **21 expected HTTP 403 responses**. Included untrusted, null, empty, wrong-port, unconfigured proxy-host, cross-site and forwarded-host spoofing cases.
- The same real-proxy run verified owner-cookie rejection, HttpOnly/SameSite flags, successful investigation, partial/failure contracts, revision conflict, saved replay with zero external calls, reset and unavailable-session behavior. Analytical execution was fixture-backed; this is live HTTP security integration, not live analytical or Gemini verification.

The first sandboxed TestClient runs stalled and were stopped; reruns with the local test runtime permissions passed. Existing developer servers were not restarted or session state reset by this work. Apply the restart above to any already-running instance.
