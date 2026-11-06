# Reproduce the backend release checks

Run commands from the repository root. The API environment uses Python 3.13. Install `requirements-api.txt` in a clean virtual environment. For provisioning and reconciliation also install `requirements-phase2b.txt`, which supplies pandas. The fixture suite uses pytest; the proxy integration test requires the frontend's locked Node dependencies.

## Disposable rehearsal

1. Start Docker Desktop's Linux engine. Install the ingestion and API packages. Ensure the repository data files are present.
2. Run `python -m scripts.rehearse_release`. It creates a uniquely named PostgreSQL 16 container from `pgvector/pgvector:0.8.2-pg16`, uses generated credentials and a loopback-only ephemeral port, then stops that container when the checks finish.
3. The initializer checks that the target database name matches and contains no application relations. It applies `db/init`, loads the explicit CSV and document manifests in `scripts/load_phase2b_v3.py`, and builds that loader's canonical views. The separate historical 010 SQL file is not a second migration step. The initializer applies migration 011, lookup indexes 012, and the review, delivery and item evidence SQL. It builds the document index using the configured embedding model, then grants the runtime login access to the named relations present in the policy.
4. The rehearsal runs `scripts.release_checks` as a separate process. The SQL corpus and MCP reads use the reader login. Independent reconciliation queries use a privileged **read-only** transaction to inspect staging inputs. The dashboard is queried over loopback HTTP. Check the process exit code and `.runtime/release_checks_disposable.json`.

## Retained installation

On an empty database in a dedicated PostgreSQL 16 cluster with pgvector available, configure `DATABASE_URL`, `MCP_DATABASE_URL`, `MCP_DB_USER` and `MCP_DB_PASSWORD` for that target. Use the standard `opslens_mcp_reader` runtime role named by migration 011. Run `python -m scripts.rehearse_release --provision-empty DATABASE_NAME`. The name must exactly match the configured database. The command refuses an occupied database and retains the successful installation. A failed partial load requires a fresh empty target.

For an existing dedicated installation, `python -m scripts.setup_phase2d_runtime_role --policy-only` reapplies grants without rotating the password. It removes reader-wide grants, future automatic grants, and the public temporary-table and indirect XML execution privileges in that database. Apply `db/migrations/012_release_lookup_indexes.sql` as the migration account. Run `python -m scripts.release_checks` and inspect `.runtime/release_checks_configured.json`. Keep the privileged account out of the API process in a deployment.

## HTTP and benchmark gates

- `GET /api/health` checks process liveness. `GET /api/ready` returns HTTP 200 only when the role, source inventory, privileges, PostgreSQL version and populated document index checks pass. Unavailable or noncompliant dependencies yield HTTP 503.
- `python -m pytest -q scripts/test_audit_cohorts.py scripts/test_audit_sql_boundary.py scripts/test_release_sql_policy.py scripts/test_release_contract.py` runs fixture tests. The contract suite uses real HTTP and the Next proxy with a temporary database for traces and a fixture executor. `node --test frontend/tests/*.test.mjs` runs the frontend suite.
- `python -m scripts.release_benchmark` runs all seven core and twelve incident questions through a fresh FastAPI process with external model credentials disabled. It writes per-run results and redacted canonical responses under `.runtime/benchmarks`. A failing release gate returns a nonzero exit status. A model-disabled run cannot satisfy the required Gemini gate.
- The separate `--gemini` mode uses `scripts.restricted_gemini_benchmark` to send only the 19 fixed benchmark questions, reviewed static instructions/schemas and allowlisted explanation labels/field references to the configured Google Gemini API. Database values and nested context stay local. Unknown instructions or references stop transmission. This restricted-input mode differs from default application prompts. Its report distinguishes observed core model calls, transport errors, descriptive measurements and independent mechanism verification. Use that mode only with authorization for that transmission.
