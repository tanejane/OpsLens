# OpsLens 5.2F — audited cohort evidence in unified reports

## Purpose
The 5.2C three-domain report still says that the February/March operational order IDs need reconciliation, despite a later independent 5.2D audit that passed in the user's own PostgreSQL instance. This additive repair makes the wording **conditional on an explicitly supplied raw and independently assessed 5.2D audit**, not on hard-coded success assumptions.

## Changes
- `agent/phase5_2c_three_domain.py`: neutral, correct default wording if no audit is attached; finance/delivery/review calculations unchanged.
- `agent/phase5_2f_cohort_evidence.py`: validates the **raw** Phase 5.2D audit with the existing deterministic assessor; checks exact report periods and order counts; enriches only the operational cohort evidence section; retains the financial/operational population distinction and all limitations.
- `agent/phase5_2e_multidomain_router.py`: optional `cohort_audit` argument; invalid explicitly supplied artifacts fail closed rather than silently elevating evidence.
- `scripts/phase5_1_playground.py`: new `--cohort-audit PATH` CLI option (opt-in).
- Updated 5.2C and 5.2E validator scripts to reflect the new neutral text and CLI call; new 5.2F negative tests.
- `scripts/phase5_2d_assess.py`: exact prior Phase 5.2D assessor for reproducible raw validation (also exists in prior package).

## Installation
Merge `agent/`, `scripts/`, `docs/` into existing repo. Back up current files or use git before replacing overlapping paths. **No DB changes or MCP grants.** Do not install individual files in isolation: 5.2C, 5.2D and 5.2E modules are prerequisites.

## Offline tests
```powershell
python -m scripts.phase5_2f_validate
python -m scripts.phase5_2c_validate
python -m scripts.phase5_2e_validate
```
Expected: `42/42`, `34/34`, and `37/37` respectively.

## Live verification using previously produced raw audit
A successful Phase 5.2D run already created `phase5_2d_cohort_audit.json` in the working directory. This must be the **raw output of the read-only PostgreSQL SQL query**, not the JSON summary printed by `phase5_2d_assess`. Recheck it first:
```powershell
python -m scripts.phase5_2d_assess .\phase5_2d_cohort_audit.json
if ($LASTEXITCODE -ne 0) { throw "Audit is not validated" }
python -m scripts.phase5_1_playground --gemini --cohort-audit .\phase5_2d_cohort_audit.json
```
In the OpsLens prompt, ask:
```
Compare finance, late delivery and review scores from February 2018 to March 2018
```
Expected combined status: `THREE_DOMAIN_DESCRIPTIVE_EVIDENCE`. New field: `operational_cohort_evidence.status = EXACT_ORDER_COHORT_RECONCILED` with February 6,728 and March 7,211. Old stale audit todo is removed. `evidence_relation` at the top remains `PERIOD_ALIGNED_SEPARATE_FINANCIAL_AND_OPERATIONAL_POPULATIONS` because finance uses a different eligible cohort.

Without the `--cohort-audit` option, the report explicitly states that no matching audit artifact is attached; it does *not* claim order-ID equality. If the supplied raw audit is malformed, from different months, or conflicts with live cohort counts, the combined route reports `MULTIDOMAIN_NOT_VALIDATED` and does not return a partially upgraded report.

## Governance limits
This is reconciliation of **base view order-ID sets** for exactly February/March 2018. It does not certify identical eligible delivery/review subsets, finance-to-operational membership, causal effects, continuous time coverage, new SQL joins or MCP authorization. It trusts that the passed raw artifact came from the separately executed read-only SQL; it cannot cryptographically authenticate an arbitrary locally edited file. Do not attach this fixed February/March artifact to unrelated time ranges.
