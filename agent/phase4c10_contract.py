"""Fail-closed validator for review order-grain audit; no MCP authorization."""

def assess(a):
    if not isinstance(a,dict) or a.get('version')!='4c10.1' or a.get('read_only') is not True or a.get('mcp_authorized') is not False or a.get('policy')!='mean_non_null_effective_scores_per_order' or a.get('time_basis')!='purchase_month':
        raise ValueError('Invalid audit provenance/policy')
    s,r,v=(a.get(k) for k in ('source','reviews','evidence'))
    if not all(isinstance(x,dict) for x in (s,r,v)) or not isinstance(a.get('months'),list): raise ValueError('Missing audit sections')
    def n(d,k):
        z=d.get(k)
        if type(z) is not int or z<0: raise ValueError('Invalid count '+k)
        return z
    for k in ('orders','unique_orders'):n(s,k)
    for k in ('review_rows','bad_scores','reviewed_ids'):n(r,k)
    for k in ('rows','unique_rows','null_keys','missing_purchase_dates','reviewed_orders','low_rating_orders','multiple_review_orders','aggregated_review_rows','mismatched_scores','mismatched_flags'):n(v,k)
    failed=[]; warnings=[]
    if not s['orders'] or not r['review_rows']:failed.append('EMPTY_EVIDENCE')
    if s['orders']!=s['unique_orders'] or v['rows']!=s['orders'] or v['unique_rows']!=v['rows'] or v['null_keys']:failed.append('ORDER_GRAIN_MISMATCH')
    if v['aggregated_review_rows']!=r['review_rows']:failed.append('REVIEW_ROWS_NOT_RECONCILED')
    if v['mismatched_scores'] or v['mismatched_flags']:failed.append('AGGREGATION_MISMATCH')
    if r['bad_scores']:failed.append('INVALID_REVIEW_SCORES')
    if v['reviewed_orders']>v['rows'] or v['low_rating_orders']>v['reviewed_orders'] or r['reviewed_ids']>v['rows']:failed.append('INVALID_DENOMINATORS')
    if v['missing_purchase_dates']:warnings.append('MISSING_PURCHASE_TIMES')
    if v['multiple_review_orders']:warnings.append('MULTIPLE_REVIEWS_AVERAGED')
    total=reviewed=low=0;last=''
    for x in a['months']:
        if not isinstance(x,dict) or not isinstance(x.get('month'),str) or len(x['month'])!=7 or x['month']<=last:raise ValueError('Invalid monthly series')
        last=x['month']; o=n(x,'orders'); rr=n(x,'reviewed_orders'); ll=n(x,'low_rating_orders')
        if not ll<=rr<=o:failed.append('INVALID_MONTHLY_DENOMINATORS')
        total+=o;reviewed+=rr;low+=ll
    if total+v['missing_purchase_dates']!=v['rows'] or reviewed>v['reviewed_orders'] or low>v['low_rating_orders']:failed.append('MONTHLY_RECONCILIATION_FAILED')
    return {'status':'ORDER_REVIEW_GRAIN_VALIDATED' if not failed else 'ORDER_REVIEW_CONTRACT_BLOCKED',
      'failures':sorted(set(failed)),'warnings':warnings,
      'counts':{'orders':v['rows'],'reviewed_orders':v['reviewed_orders'],'low_rating_orders':v['low_rating_orders'],'multiple_review_orders':v['multiple_review_orders'],'purchase_months':len(a['months'])},
      'approved_for_mcp':False,'causal_claim':False,
      'next_gate':'Approve metric definitions and coverage, validate MCP read role and governed parameterized executor'}
