"""Phase 5.2E: bounded three-domain routing adapter for the unified OpsLens CLI.

Only explicit finance + delivery + satisfaction questions with two verifiable
purchase-months may enter the existing, independently governed 5.2C executor.
No Gemini-generated SQL, new joins, permissions, or causal attribution.
"""
from __future__ import annotations
import re
from agent.phase5_2f_cohort_evidence import apply_cohort_evidence, CohortEvidenceRejected
from agent.phase5_2c_three_domain import periods_of, ThreeDomainRejected, investigate

MONTHS = ('January','February','March','April','May','June','July','August','September','October','November','December')
M = '|'.join(MONTHS)
PAIR = re.compile(r'\b(?:' + M + r')\s+20\d{2}\b', re.I)
SHARED_YEAR = re.compile(r'\b(?:from\s+|between\s+)(?P<first>' + M + r')\s+(?:to|and)\s+(?P<second>' + M + r')\s+(?P<year>20\d{2})\b', re.I)
FINANCE = re.compile(r'\b(?:financ\w*|revenue|reveneu|profit|profitt|cogs|marketing\s+(?:cost|expense))\b', re.I)
DELIVERY = re.compile(r'\b(?:delivery|deliveries|delivry|lateness|late\s+(?:delivery|deliveries))\b', re.I)
SATISFACTION = re.compile(r'\b(?:reviews?|ratings?|satisfaction|customer\s+experience)\b', re.I)
CAUSE = re.compile(r'\b(?:caus\w*|responsible\s+for|prove|because\s+of|attribut\w*|impact\w*|led\s+to)\b', re.I)
UNSAFE = re.compile(r'(;|--|/\*|\*/|\b(?:drop|delete|insert|update|alter|grant|revoke)\b|ignore\s+(?:all\s+)?(?:previous|prior)\s+instructions)', re.I)


def decision(question):
    """Return (decision, canonical, reason); None if unrelated to 3-domain scope.

    For a relevant but malformed request, fail closed. Never silently fall back
    to a single-domain executor which might reinterpret the user's intent.
    """
    if not isinstance(question, str) or not question.strip():
        return None
    # An unrelated one-/two-domain question must never be hijacked just because
    # it contains a semicolon. Only validate the three-domain contract in scope.
    if not all((FINANCE.search(question), DELIVERY.search(question), SATISFACTION.search(question))):
        return None
    if len(question) > 500 or UNSAFE.search(question):
        return ('reject', None, 'Unsafe or invalid multi-domain input')
    if CAUSE.search(question):
        return ('reject', None, 'Causal attribution is not supported by the three-domain descriptive contract')
    canonical = question.strip()
    explicit = PAIR.findall(canonical)
    shared = SHARED_YEAR.search(canonical)
    if shared and len(explicit) != 1:
        return ('reject', None, 'Shared-year range contains extra or inconsistent dated months')
    if len(explicit) == 1 and shared:
        # Shared-year range is corroborated by two literal month names and a single year.
        a,b,y=shared.group('first','second','year')
        canonical = canonical[:shared.start()] + f'from {a} {y} to {b} {y}' + canonical[shared.end():]
    elif len(explicit) != 2:
        return ('reject', None, 'Specify both comparison months and years, or an explicit shared-year range')
    try:
        periods_of(canonical)  # independently checks ordering, calendar boundaries and safety
    except ThreeDomainRejected as exc:
        return ('reject', None, f'Comparison periods not validated: {exc}')
    return ('execute', canonical, None)


def _blocked(reason):
    return {'route':'three_domain_investigation','status':'NEEDS_CLARIFICATION',
            'executable':False,'approved_for_mcp':False,'causal_claim':False,
            'inventory_claim_allowed':False,'reason':reason}


async def route(question, existing_dispatch, reader, finance_investigator, *, cohort_audit=None):
    """Intercept only scoped 3-domain requests, otherwise preserve existing routes.

    existing_dispatch is a zero-argument async callable. reader is the existing
    governed SQL reader and finance_investigator is the existing Phase 4C.7 path.
    """
    d=decision(question)
    if d is None:
        return await existing_dispatch()
    mode,canonical,reason=d
    if mode!='execute':
        return _blocked(reason)
    try:
        report=await investigate(canonical,reader,finance_investigator)
    except Exception as exc:
        # Do not return partial evidence or silently downgrade to an unrelated path.
        return {'route':'three_domain_investigation','status':'MULTIDOMAIN_NOT_VALIDATED',
                'executable':False,'approved_for_mcp':False,'causal_claim':False,
                'inventory_claim_allowed':False,'error_type':type(exc).__name__,
                'reason':str(exc)[:240]}
    if not isinstance(report,dict) or report.get('status')!='THREE_DOMAIN_DESCRIPTIVE_EVIDENCE' or report.get('causal_claim') is not False:
        return _blocked('Existing cross-domain executor did not produce a validated descriptive report')
    try:
        report=apply_cohort_evidence(report,cohort_audit)
    except CohortEvidenceRejected as exc:
        return {'route':'three_domain_investigation','status':'MULTIDOMAIN_NOT_VALIDATED',
                'executable':False,'approved_for_mcp':False,'causal_claim':False,
                'inventory_claim_allowed':False,'reason':'COHORT_AUDIT_INVALID: '+str(exc)[:160]}
    return {**report,'unified_multidomain':{'original_question':question,
                'validated_request':canonical,'policy':'three_domain_explicit_periods_v1',
                'gemini_executed_tools':False}}
