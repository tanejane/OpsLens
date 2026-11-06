"""Fail-closed validation of read-only CX/delivery source audits.

This phase does NOT approve an operational metric or a join path for MCP.
"""
from __future__ import annotations


def assess(audit: dict) -> dict:
    if not isinstance(audit, dict) or audit.get('audit_version') != '4c9.1' or audit.get('query_type') != 'read_only':
        raise ValueError('Unrecognized audit proof')
    if audit.get('source_views') != ['commerce.orders', 'operations.delivery_effective', 'cx.effective_reviews']:
        raise ValueError('Unrecognized source views')
    for key in ('orders', 'delivery', 'reviews'):
        if not isinstance(audit.get(key), dict):
            raise ValueError(f'Missing {key} evidence')
    def count(obj, key):
        n = obj.get(key)
        if isinstance(n, bool) or not isinstance(n, int) or n < 0:
            raise ValueError(f'Invalid count: {key}')
        return n
    o,d,r = [audit[k] for k in ('orders','delivery','reviews')]
    for obj in (o,d,r):
        for key in ('rows','unique_orders','null_keys'):
            count(obj,key)
        if obj['unique_orders'] > obj['rows']:
            raise ValueError('Impossible population counts')
    fails=[]; warnings=[]
    if o['rows'] == 0 or d['rows']==0 or r['rows']==0: fails.append('EMPTY_REQUIRED_SOURCE')
    if o['rows'] != o['unique_orders'] or o['null_keys']: fails.append('ORDER_GRAIN_INVALID')
    if d['rows'] != d['unique_orders'] or d['null_keys']: fails.append('DELIVERY_GRAIN_INVALID')
    if d['unique_orders'] != o['unique_orders']: fails.append('DELIVERY_ORDER_COVERAGE_MISMATCH')
    for label in ('review_orphans','delivery_orphans'):
        if count(audit,label): fails.append(label.upper())
    for label in ('out_of_range_score','out_of_range_raw_score'):
        if count(r,label): fails.append(label.upper())
    if count(d,'negative_elapsed'): fails.append('NEGATIVE_DELIVERY_ELAPSED')
    for label in ('missing_delivered','missing_estimated','missing_purchased'):
        if count(d,label): warnings.append(label.upper())
    if count(r,'missing_score'): warnings.append('MISSING_REVIEW_SCORES')
    card=audit.get('review_cardinality')
    if not isinstance(card,dict): raise ValueError('Missing review grain audit')
    multi=count(card,'multi_review_orders'); maximum=count(card,'max_reviews_per_order')
    if maximum>r['rows'] or (multi>0 and maximum<2) or (multi==0 and maximum!=0):
        raise ValueError('Inconsistent review multiplicity')
    if multi: warnings.append('MULTIPLE_REVIEWS_PER_ORDER_REQUIRE_AGGREGATION')
    cover=audit.get('coverage')
    if not isinstance(cover,dict): raise ValueError('Missing coverage')
    observed=count(cover,'reviewed_delivered_orders')
    if observed>min(d['unique_orders'],r['unique_orders']): raise ValueError('Impossible overlap')
    if observed==0: warnings.append('NO_REVIEWED_DELIVERED_ORDER_OVERLAP')
    if not fails:
        warnings.append('AUDIT_ONLY_NO_METRIC_OR_JOIN_AUTHORIZATION')
    return {'status':'AUDIT_BLOCKED' if fails else 'SOURCE_GRAIN_AUDIT_PASSED',
            'failures':fails,'warnings':warnings,'evidence':{
              'orders':o['unique_orders'],'delivery_orders':d['unique_orders'],
              'reviewed_orders':r['unique_orders'],'reviewed_delivered_orders':observed,
              'multi_review_orders':multi,'delivery_missing_dates':d['missing_delivered']},
            'approved_for_mcp':False,'causal_claim':False,
            'next_gate':'Review and validate an order-grain aggregation, metric definitions, denominators, time coverage and MCP allowlist.'}
