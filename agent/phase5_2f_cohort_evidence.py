"""Explicit, independently assessed cohort evidence for descriptive reports.

Not authorization for new cross-domain joins, finance cohort equality, or causality.
"""
from __future__ import annotations
from copy import deepcopy
import json
from pathlib import Path
from scripts.phase5_2b_assess import assess as assess_may_june
from scripts.phase5_2d_assess import assess as assess_february_march

class CohortEvidenceRejected(ValueError):
    pass

def load_audit(path):
    """Load raw 5.2D audit, not a summary or a user-authored 'success' badge."""
    try:
        payload=json.loads(Path(path).read_text(encoding='utf-8-sig'))
    except (OSError,ValueError,TypeError) as exc:
        raise CohortEvidenceRejected('AUDIT_FILE_UNREADABLE_OR_INVALID') from exc
    return payload

def apply_cohort_evidence(report, raw_audit):
    if not isinstance(report,dict) or report.get('status')!='THREE_DOMAIN_DESCRIPTIVE_EVIDENCE' or report.get('causal_claim') is not False or report.get('approved_for_mcp') is not False:
        raise CohortEvidenceRejected('REPORT_CONTRACT_INVALID')
    output=deepcopy(report)
    if raw_audit is None:
        output['operational_cohort_evidence']={'status':'NOT_ATTACHED','exact_order_id_sets_verified':False}
        return output
    try:
        assessor = {
            'PHASE5_2B_EXACT_ORDER_COHORT_V1': assess_may_june,
            'PHASE5_2D_EXACT_ORDER_COHORT_V1': assess_february_march,
        }[raw_audit['contract']]
        result=assessor(raw_audit)
    except (TypeError,KeyError,ValueError) as exc:
        raise CohortEvidenceRejected('RAW_AUDIT_VALIDATION_FAILED') from exc
    if result.get('status')!='EXACT_ORDER_COHORT_RECONCILED' or result.get('failures')!=[]:
        raise CohortEvidenceRejected('AUDIT_NOT_RECONCILED')
    periods=output.get('periods')
    if not isinstance(periods,dict) or set(periods)!={'before','after'}:
        raise CohortEvidenceRejected('REPORT_PERIODS_INVALID')
    months=result['months']
    expected_periods = [[p['month_start'], p['month_end']] for p in raw_audit['month_pairs']]
    if [periods['before'], periods['after']] != expected_periods:
        raise CohortEvidenceRejected('PERIOD_MISMATCH')
    for m in months:
        if m.get('delivery_id_set_equal') is not True or m.get('review_id_set_equal') is not True:
            raise CohortEvidenceRejected('ORDER_ID_SETS_NOT_EQUAL')
    counts=output.get('cohort_orders')
    if not isinstance(counts,dict) or set(counts)!={'before','after'} or any(type(counts[k]) is not int for k in ('before','after')) or [counts['before'],counts['after']] != [m['orders'] for m in months]:
        raise CohortEvidenceRejected('COHORT_COUNT_MISMATCH')
    output['operational_cohort_evidence']={
        'source_artifact':deepcopy(raw_audit),
        'assessment':deepcopy(result),
        'status':'EXACT_ORDER_COHORT_RECONCILED',
        'evidence_relation':'SAME_PURCHASE_MONTH_ORDER_ID_SETS_VALIDATED',
        'exact_order_id_sets_verified':True,
        'months':deepcopy(months),
        'scope':'delivery_and_review_base_views_only',
        'audit_contract':raw_audit['contract'],
        'approved_for_mcp':False,'causal_claim':False,
        'limitation':'Does not validate equal finance order populations or equal metric-specific eligible subsets'
    }
    output['next_validations']=[s for s in output['next_validations'] if not ('exact' in s.lower() and 'order' in s.lower())]
    output['limitations']=[s for s in output['limitations'] if 'order-ID audit for the requested periods has not been attached' not in s]
    output['conclusions'].append('Delivery and review base views have independently reconciled exact order-ID sets for these two purchase months; eligible metric subsets may differ')
    output['tool_trace'].append({'capability':'independent_read_only_order_cohort_audit_artifact','status':'EXACT_ORDER_COHORT_RECONCILED','executed_new_sql':False})
    # Top-level evidence_relation remains distinct to avoid implying finance population equality.
    return output
