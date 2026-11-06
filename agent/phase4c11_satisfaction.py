"""Governed, purchase-cohort satisfaction metrics from audited order-review view.

No LLM-generated SQL, writes, auto-grants or causal inference.
The deployment owner must separately audit and approve MCP role visibility.
"""
from __future__ import annotations
from agent.investigation_result import retain_validated
from datetime import date
from decimal import Decimal, InvalidOperation
import re

SOURCE = 'semantic.order_review_evidence_v1'
POLICY = 'mean_non_null_effective_scores_per_order'
METRICS = {
    'average_review_score': ('average_score', 'score_1_to_5'),
    'low_rating_rate': ('low_rating_rate_pct', 'percent'),
    'review_coverage': ('review_coverage_pct', 'percent'),
    'reviewed_order_count': ('reviewed_orders', 'orders'),
}
DATE_RX = re.compile(r'^\d{4}-\d{2}-\d{2}$')
class ReviewRejected(ValueError): pass

def period(start: str, end: str) -> tuple[str,str]:
    if not isinstance(start,str) or not isinstance(end,str) or not DATE_RX.fullmatch(start) or not DATE_RX.fullmatch(end):
        raise ReviewRejected('Dates must be ISO YYYY-MM-DD')
    try: a,b=date.fromisoformat(start),date.fromisoformat(end)
    except ValueError as e: raise ReviewRejected('Invalid dates') from e
    if a>=b or (b-a).days>366: raise ReviewRejected('Require positive interval <=366 days')
    return start,end

def compile_metric(metric_id: str, start: str, end: str) -> dict:
    if metric_id not in METRICS: raise ReviewRejected('Unregistered review metric')
    start,end=period(start,end)
    # SQL literals are safe only after strict canonical ISO validation above.
    sql=f"""SELECT COUNT(*)::bigint AS eligible_orders,
COUNT(*) FILTER (WHERE has_review)::bigint AS reviewed_orders,
COUNT(*) FILTER (WHERE low_rating)::bigint AS low_rating_orders,
COUNT(*) FILTER (WHERE review_records > 1)::bigint AS multi_review_orders,
AVG(order_score) FILTER (WHERE has_review) AS average_score,
(100.0 * COUNT(*) FILTER (WHERE low_rating) / NULLIF(COUNT(*) FILTER (WHERE has_review),0)) AS low_rating_rate_pct,
(100.0 * COUNT(*) FILTER (WHERE has_review) / NULLIF(COUNT(*),0)) AS review_coverage_pct,
COUNT(DISTINCT order_id)::bigint AS distinct_orders,
COUNT(*) FILTER (WHERE order_score IS NOT NULL AND (order_score < 1 OR order_score > 5))::bigint AS invalid_scores,
COUNT(*) FILTER (WHERE (has_review IS DISTINCT FROM (order_score IS NOT NULL)) OR
 (low_rating IS DISTINCT FROM COALESCE(order_score <= 2, false)))::bigint AS invalid_flags
FROM {SOURCE}
WHERE purchase_time >= DATE '{start}' AND purchase_time < DATE '{end}'"""
    return {'metric_id':metric_id,'start':start,'end':end,'source':SOURCE,'sql':sql,
            'policy':POLICY,'time_basis':'order_purchase_time', 'max_rows':1,'causal_claim':False}

def _whole(row:dict,key:str)->int:
    v=row.get(key)
    if type(v) is int: n=v
    elif isinstance(v,str) and re.fullmatch(r'\d+',v): n=int(v)
    else:raise ReviewRejected('Invalid integer '+key)
    if n<0:raise ReviewRejected('Negative '+key)
    return n

def _num(row,key,nullable=False):
    v=row.get(key)
    if v is None:
        if nullable:return None
        raise ReviewRejected('Null '+key)
    if isinstance(v,bool):raise ReviewRejected('Boolean numeric '+key)
    try:n=Decimal(str(v))
    except (InvalidOperation, ValueError):raise ReviewRejected('Invalid decimal '+key)
    if not n.is_finite():raise ReviewRejected('Nonfinite '+key)
    return n

@retain_validated
def validate_metric(plan:dict,response:dict)->dict:
    if not isinstance(plan,dict) or plan.get('policy')!=POLICY or plan.get('time_basis')!='order_purchase_time' or plan.get('source')!=SOURCE:
        raise ReviewRejected('Untrusted plan provenance')
    exact=compile_metric(plan['metric_id'],plan['start'],plan['end'])
    if plan!=exact:raise ReviewRejected('Tampered query plan')
    if not isinstance(response,dict) or not isinstance(response.get('rows'),list) or len(response['rows'])!=1 or not isinstance(response['rows'][0],dict):
        raise ReviewRejected('Expected exactly one aggregate row')
    r=response['rows'][0]; total=_whole(r,'eligible_orders'); reviewed=_whole(r,'reviewed_orders'); low=_whole(r,'low_rating_orders')
    duplicate=_whole(r,'multi_review_orders'); distinct=_whole(r,'distinct_orders')
    if not total:raise ReviewRejected('NO_SOURCE_COVERAGE')
    if distinct!=total or not 0<=low<=reviewed<=total or duplicate>total:raise ReviewRejected('Order grain/denominator violation')
    if _whole(r,'invalid_scores') or _whole(r,'invalid_flags'):raise ReviewRejected('Invalid source scores/flags')
    avg=_num(r,'average_score',True); low_pct=_num(r,'low_rating_rate_pct',True); coverage_pct=_num(r,'review_coverage_pct')
    tolerance=Decimal('0.00001')
    if not 0<=coverage_pct<=100 or abs(coverage_pct-Decimal(100)*reviewed/total)>tolerance:raise ReviewRejected('Coverage mismatch')
    if reviewed:
        if avg is None or low_pct is None or not 1<=avg<=5 or not 0<=low_pct<=100 or abs(low_pct-Decimal(100)*low/reviewed)>tolerance:
            raise ReviewRejected('Score/rate mismatch')
    elif any(x is not None for x in (avg,low_pct)) or low:
        raise ReviewRejected('Invalid empty-reviewed population')
    value={'average_review_score':avg, 'low_rating_rate':low_pct,'review_coverage':coverage_pct,'reviewed_order_count':Decimal(reviewed)}[plan['metric_id']]
    if value is None:raise ReviewRejected('NO_REVIEW_COVERAGE')
    return {'status':'MEASURED_WITH_SCOPE_LIMITS','metric_id':plan['metric_id'],'value':str(value),
        'unit':METRICS[plan['metric_id']][1], 'source':SOURCE, 'period':[plan['start'],plan['end']],
        'population':{'eligible_orders':total,'reviewed_orders':reviewed,'low_rating_orders':low,'multi_review_orders':duplicate},
        'policy':POLICY, 'time_basis':'order_purchase_time','causal_claim':False,
        'limitations':['Purchase-time cohorts, not review-submission-time cohorts',
          'Effective review scores may include modeled incident adjustments',
          'Nonempty source data do not certify continuous coverage',
          'Order-level mean of non-null scores is a documented modeling choice, not a unique ground truth']}

async def measure(metric_id,start,end,reader):
    """reader(sql,purpose)->one aggregate dict; caller manages MCP allowlist & roles."""
    plan=compile_metric(metric_id,start,end)
    row=await reader(plan['sql'], '4C11 governed order-review metric '+metric_id)
    return validate_metric(plan,{'rows':[row]})
