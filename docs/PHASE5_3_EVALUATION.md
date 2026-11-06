# Phase 5.3A — Core regression evaluation

## Scope
This package adds **one evaluation harness**; it does not update production routers, metric definitions, database views, MCP grants or Gemini prompts. It tests the *existing* unified agent. The objective is to distinguish (a) offline safety/contract checks, (b) live observed behavior, and (c) incident evaluation that has **not** yet been executed.

### Prerequisites
Merge this package's `scripts/` and `docs/` into your existing OpsLens repository after Phase 5.2F. Do not replace pre-existing files. Use Python from the repository root. Existing Gemini credentials and local PostgreSQL/MCP setup are required for live execution. The live runner can make paid Gemini requests; opt in with `--gemini`.

### Offline checks (no network, Gemini, MCP, database)

```powershell
python -m scripts.phase5_3_eval offline --output .\reports\phase5_3_offline.json
```

These checks exercise the installed Phase 5.2E router and test negative/tampered evaluation outputs. They **do not** establish live accuracy or tool reliability. The scoring result should be `OFFLINE_CONTRACTS_PASSED`.

### Live, deterministic unified agent (actual local MCP)

```powershell
python -m scripts.phase5_3_eval live --cohort-audit .\phase5_2d_cohort_audit.json --output .\reports\phase5_3_live_deterministic.json --timeout 300
```

### Live, Gemini-enabled unified agent (API usage, costs may apply)

```powershell
python -m scripts.phase5_3_eval live --gemini --cohort-audit .\phase5_2d_cohort_audit.json --output .\reports\phase5_3_live_gemini.json --timeout 480
```

The live runner starts the same `scripts.phase5_1_playground` CLI via a child process and sends seven fixed English cases in order. Cases include typos, a delivery metric, metric ambiguity, multi-domain explicit and shared-year comparisons, a rejected causal assertion, and return to a single domain. It records assertion failures and status; it does **not** claim to test every possible user request.

Results are saved under `reports/`. Each case compares observed route, status, permission and causal limits, expected metric/period/value (where verified), and the cohort artifact scope for the two three-domain questions. A live failure returns a nonzero process exit code. SDK logs are ignored during JSON extraction; hash of stdout/stderr is recorded rather than full potentially sensitive text. Examine the report for individual failed checks.

The numeric anchors are based on the specifically live-validated June 2018 and February–March 2018 results. Do not reuse the anchors with a different database. This is a regression suite, **not** a generalization benchmark.

### 12 incident fixtures — deliberately not yet scored

The optional inventory looks for `data/eval_ground_truth/incident_001.json` through `incident_012.json`. It reports only file presence. **File presence does not mean an incident was executed or evaluated.** Incident-scoring requires separate run records, each with an executed investigation trace and manually reviewed ground truth. It is a distinct next gate; do not report 12/12 incident accuracy from this package.

### Limitations and security

- No new SQL or MCP authority is granted; live execution uses the existing local MCP client.
- One pass per case, in one conversation, is not a statistically valid estimate of reliability, and model results can vary across runs.
- Individual output checks cannot certify all tool-internal behavior. Inspect actual tool traces for deep security audit.
- Case suite is fixed and narrow. A separate held-out adversarial and incident suite is still required.
- The existing Feb/Mar cohort audit supports delivery/review base-view ID equality only; not finance equality or causal claims.
- Audit input is an actual previously reconciled raw JSON file; do not fabricate it for passing results.
