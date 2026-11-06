"""Independent fail-closed check of Phase 5.2D cohort audit JSON."""
import json
import sys
from pathlib import Path

class CohortAuditRejected(ValueError):
    pass

DATES = [('2018-02-01','2018-03-01'),('2018-03-01','2018-04-01')]
COUNTS = ('source_rows','source_unique_orders','delivery_rows','delivery_unique_orders',
          'review_rows','review_unique_orders','missing_delivery_orders',
          'missing_review_orders','extra_delivery_orders','extra_review_orders',
          'delivery_only_orders','review_only_orders',
          'delivery_purchase_timestamp_mismatches','review_purchase_timestamp_mismatches')
GLOBAL = ('delivery_null_order_ids','review_null_order_ids','source_null_order_ids',
          'delivery_duplicate_order_ids','review_duplicate_order_ids','source_duplicate_order_ids',
          'delivery_missing_purchase_time','review_missing_purchase_time')

def assess(data):
    if not isinstance(data,dict) or set(data) != {'contract','time_basis','month_pairs','global_quality','read_only','approved_for_mcp','causal_claim'}:
        raise CohortAuditRejected('INVALID_AUDIT_ENVELOPE')
    if data['contract'] != 'PHASE5_2D_EXACT_ORDER_COHORT_V1' or data['time_basis'] != 'order_purchase_time' or data['read_only'] is not True or data['approved_for_mcp'] is not False or data['causal_claim'] is not False:
        raise CohortAuditRejected('INVALID_CONTRACT_OR_AUTHORIZATION')
    periods=data['month_pairs'];quality=data['global_quality']
    if not isinstance(periods,list) or len(periods)!=2 or not isinstance(quality,dict) or set(quality)!=set(GLOBAL):
        raise CohortAuditRejected('INVALID_COHORT_STRUCTURE')
    failures=[]
    for k in GLOBAL:
        v=quality[k]
        if type(v) is not int or v<0:raise CohortAuditRejected('INVALID_GLOBAL_COUNT_'+k)
        if v:failures.append('GLOBAL_'+k.upper())
    checked=[]
    for ix,p in enumerate(periods):
        if not isinstance(p,dict) or set(p)!={'month_start','month_end',*COUNTS}:
            raise CohortAuditRejected('INVALID_MONTH_SCHEMA')
        if (p['month_start'],p['month_end'])!=DATES[ix]:
            raise CohortAuditRejected('UNEXPECTED_MONTH_OR_ORDER')
        for k in COUNTS:
            if type(p[k]) is not int or p[k]<0:raise CohortAuditRejected('INVALID_MONTH_COUNT_'+k)
        if p['source_rows']<=0:failures.append('EMPTY_SOURCE_'+p['month_start'])
        if p['source_rows']!=p['source_unique_orders']:failures.append('SOURCE_GRAIN_'+p['month_start'])
        if p['delivery_rows']!=p['delivery_unique_orders']:failures.append('DELIVERY_GRAIN_'+p['month_start'])
        if p['review_rows']!=p['review_unique_orders']:failures.append('REVIEW_GRAIN_'+p['month_start'])
        if p['source_unique_orders']!=p['delivery_unique_orders'] or p['source_unique_orders']!=p['review_unique_orders']:
            failures.append('MONTH_COHORT_COUNT_MISMATCH_'+p['month_start'])
        for k in COUNTS[6:]:
            if p[k]:failures.append(k.upper()+'_'+p['month_start'])
        checked.append({'month':p['month_start'],'orders':p['source_unique_orders'],
                        'delivery_id_set_equal':p['missing_delivery_orders']==p['extra_delivery_orders']==0,
                        'review_id_set_equal':p['missing_review_orders']==p['extra_review_orders']==0})
    return {'status':'EXACT_ORDER_COHORT_RECONCILED' if not failures else 'EXACT_ORDER_COHORT_RECONCILIATION_FAILED',
            'failures':failures,'months':checked,
            'evidence_relation':'SAME_PURCHASE_MONTH_ORDER_ID_SETS_VALIDATED' if not failures else 'ORDER_ID_COHORT_NOT_VALIDATED',
            'causal_claim':False,'approved_for_mcp':False,
            'next_gate':'Run vetted 5.2C finance/operations comparison and independently validate numeric evidence; do not infer financial-order population equality or causation'}

def main(argv=None):
    argv=sys.argv[1:] if argv is None else argv
    try:
        if len(argv)!=1:raise CohortAuditRejected('USAGE: python -m scripts.phase5_2d_assess audit.json')
        payload=json.loads(Path(argv[0]).read_text(encoding='utf-8-sig'))
        out=assess(payload)
    except (ValueError,OSError,json.JSONDecodeError) as exc:
        out={'status':'EXACT_ORDER_COHORT_RECONCILIATION_FAILED','failures':[str(exc)],'approved_for_mcp':False,'causal_claim':False}
    print(json.dumps(out,indent=2))
    return 0 if out['status']=='EXACT_ORDER_COHORT_RECONCILED' else 1

if __name__=='__main__':raise SystemExit(main())
