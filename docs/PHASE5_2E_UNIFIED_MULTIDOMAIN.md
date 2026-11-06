# Phase 5.2E — Unified three-domain investigation routing

## Scope
An additive router connects the validated Phase 5.2C finance + delivery + satisfaction investigator to the existing Phase 5.1 unified CLI. It does not register a new MCP tool or authorize cross-domain SQL joins. The new adapter uses the existing Phase 4C.7 bounded finance investigator, read-only MCP reader, and Phase 5.2C independent per-domain measurement contracts.

Supported request formats include:

- `Compare finance, late delivery and review scores from February 2018 to March 2018`
- `Revenue increased but profit fell between February and March 2018. Did delivery and customer satisfaction also get worse?`

The second format is converted to a two-explicit-date query **only** when the user's text contains a single unambiguous shared-year range. Both dates must be explicitly grounded. No model may invent a missing date, metric, or category. A question asking for causal attribution is blocked; observational simultaneous deterioration is permitted as descriptive evidence.

## Installation
Merge `agent/`, `scripts/`, and `docs/` into the existing OpsLens repository. Replace only `scripts/phase5_1_playground.py` with the supplied version. The existing `agent/phase5_1_unified.py` is unchanged. **Prerequisites**: completed, previously installed Phase 5.1C and Phase 5.2C packages, the governed MCP reader, current database views and existing Gemini API credentials for finance investigation.

No database migration, SQL-policy changes, user grants, or MCP allowlist modifications.

## Offline checks

```powershell
python -m scripts.phase5_2e_validate
python -m scripts.phase5_2c_validate
python -m scripts.phase5_1_validate
python -m scripts.phase5_1b_validate
python -m scripts.phase5_1c_validate
```

## Live verification

```powershell
python -m scripts.phase5_1_playground --gemini
```

Type in the playground:

```
Compare finance, late delivery and review scores from February 2018 to March 2018
Revenue increased but profit fell between February and March 2018. Did delivery and customer satisfaction also get worse?
What was the late delivery rate in June 2018?
Why did delivery delays cause poor reviews and profit decline between February and March 2018?
```

Expected: First two return `THREE_DOMAIN_DESCRIPTIVE_EVIDENCE` **if live measurements independently pass all the previous contracts**. Third delegates to the preexisting delivery router. Fourth is blocked without calling governed tools. A successful report has `causal_claim: false` and `approved_for_mcp: false` (the combined capability is not separately MCP-authorized). Review output values and periods; the status alone is insufficient for semantic acceptance. The February/March exact cohort audit (Phase 5.2D) was separately validated by the user, but this router does not independently re-run the audit, so the report continues to state population limitations and must not claim finance population equivalence.

## Security and reliability notes

- Preflight is deliberately **not Gemini-driven** for this narrow, auditable three-domain request type. Existing Gemini finance inference still occurs inside the governed finance investigator as previously validated.
- Only fully explicit, chronological two-month questions are accepted. Shared-year expansion retains both original and canonical text in the result.
- Unexpected executor failures return `MULTIDOMAIN_NOT_VALIDATED`; they are never silently downgraded to single-domain responses.
- Unknown/unsupported topics are passed to the original unified session unchanged.
- Other multi-domain combinations and arbitrary comparative questions are out of scope. No statistical causality, approval for new joins, or inventory data are claimed.
