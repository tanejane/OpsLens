# Phase 5.2C — bounded three-domain investigation

## Preconditions
- Phase 4C.7 audited finance investigation; Phase 4C.11 review and 4C.15 delivery metric compilers and their live MCP reader must be installed and authorized.
- Phase 5.2A two-domain comparison is installed. Phase 5.2B exact order-ID reconciliation is **only certified for May and June 2018**; it cannot be used to claim exact February/March cohort membership.
- Finance, delivery, and reviews have different metric eligibility denominators; this is a **descriptive evidence comparison**, not a governed cross-domain join or causal explanation.

## Install
Merge `agent/`, `scripts/` and `docs/` into the existing OpsLens repo. No database migrations, role grants, allowlist changes or replacements of existing executors.

## Offline contract checks
`python -m scripts.phase5_2c_validate`

## Live test
`python -m scripts.phase5_2c_live "Compare finance, late delivery and review scores from February 2018 to March 2018"`

Expected successful **shape** (numbers depend on live source): `THREE_DOMAIN_DESCRIPTIVE_EVIDENCE`, with finance premise, cost-component accounting hypotheses (only if reconciled), operational metric changes, limitations and bounded tool trace. If a live dependency fails, `THREE_DOMAIN_NOT_VALIDATED` is correct and nothing should be represented as reconciled.

Financial premise is verified first. The bounded finance investigator may consult Gemini for natural-language interpretation, but Gemini cannot execute SQL. Existing read-only MCP compilers govern every SQL statement. No cross-domain SQL joins are introduced.

## Not approved
- Causal claims that delivery or reviews explain changes in contribution profit.
- Equivalent order-ID populations across finance / delivery / reviews.
- New finance-to-review joins or a new MCP capability approval.
- Inventory claims, campaign incrementality, or product category profit allocation.

## Next gate
Run a **period-specific** February/March order-ID reconciliation and compare period-specific eligible denominators before making stronger cross-domain cohort statements. Once live verified, integrate this bounded multi-domain route into the unified agent and incident evaluation harness.
