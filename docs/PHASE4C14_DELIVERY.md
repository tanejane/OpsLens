# Phase 4C.14 — delivery evidence audit (not an approved metric executor)

## Scope
- Source: `operations.delivery_effective` (previous 4C.9 source-grain audit confirmed one row/order in that snapshot).
- Derived view: `semantic.order_delivery_evidence_v1`, one row/order, with **effective** delivered-customer timestamp (can contain controlled incident adjustments), estimated delivery timestamp, and purchase timestamp.
- Time basis for future metrics: purchase date. **Late** means `actual delivered > estimated delivered`, not `>=`; only when **both** dates exist. Missing actual or estimate is **unknown**, never on-time.
- Delivery duration: elapsed days `actual delivered - purchase` for orders with both timestamps and nonnegative elapsed time; negative elapsed is an audit failure.
- Rate denominators are different: `late_orders / lateness_eligible`, while delivery-duration mean uses `duration_eligible`. Do not substitute all orders or reviewed orders.
- The view is an audit artifact, **not approved for MCP**. No permissions granted, no allowlist modifications, no NLP routing changes, no causal claims.
- No inference of actual carrier SLAs, refund entitlement, distribution completeness or causality.

## Install and validate
Merge the package folders at the repository root. Run:

```powershell
python -m scripts.phase4c14_validate
$dbUser=(docker exec opslens-postgres printenv POSTGRES_USER).Trim()
Get-Content .\sql\phase4c14_delivery_view.sql -Raw | docker exec -i opslens-postgres psql -X -U $dbUser -d opslens -v ON_ERROR_STOP=1
if ($LASTEXITCODE -ne 0) { throw 'Delivery view creation failed' }
Get-Content .\sql\phase4c14_delivery_audit.sql -Raw | docker exec -i opslens-postgres psql -X -q -t -A -U $dbUser -d opslens -v ON_ERROR_STOP=1 | Set-Content .\phase4c14_audit.json -Encoding utf8
if ($LASTEXITCODE -ne 0) { throw 'Delivery audit failed' }
python -m scripts.phase4c14_assess .\phase4c14_audit.json
```

Expected `DELIVERY_EVIDENCE_AUDIT_PASSED` **only if** raw and derived counts reconcile. The assessor deliberately returns `approved_for_mcp: false`. Compare actual data and any warnings before proceeding to a governed delivery metric executor, role permission check, and MCP allowlist audit.

## Notes
The view casts timestamp-like source fields; this assumes the previously audited source contains parseable timestamps. If it does not, the migration will fail rather than inventing missing values. Reconciliation is independent at the expression/source level, but source view and derived view share upstream data; this is not independent provenance certification.
