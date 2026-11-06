"""Governed delivery metrics: audited order grain, purchase-time cohorts, no causal claims."""
from agent.investigation_result import retain_validated
from datetime import date
from decimal import Decimal, InvalidOperation
import re

SOURCE='semantic.order_delivery_evidence_v1'
POLICY='late_iff_actual_gt_estimated_on_eligible_orders'
METRICS={'late_delivery_rate':('late_rate_pct','percent'), 'average_delivery_days':('mean_delivery_days','days'), 'delivered_order_count':('duration_eligible_orders','orders'), 'delivery_evidence_coverage':('lateness_coverage_pct','percent')}
class DeliveryRejected(ValueError): pass

def period(start,end):
    if not isinstance(start,str) or not isinstance(end,str) or not re.fullmatch(r'\d{4}-\d{2}-\d{2}',start) or not re.fullmatch(r'\d{4}-\d{2}-\d{2}',end): raise DeliveryRejected('Dates must be ISO YYYY-MM-DD')
    try: a,b=date.fromisoformat(start),date.fromisoformat(end)
    except ValueError as e: raise DeliveryRejected('Invalid dates') from e
    if a>=b or (b-a).days>366: raise DeliveryRejected('Require positive interval <=366 days')
    return start,end

def compile_metric(metric_id,start,end):
    if not isinstance(metric_id,str) or metric_id not in METRICS: raise DeliveryRejected('Unregistered delivery metric')
    start,end=period(start,end)
    sql=f"""SELECT COUNT(*)::bigint AS eligible_orders,
COUNT(DISTINCT order_id)::bigint AS distinct_orders,
COUNT(*) FILTER (WHERE lateness_eligible)::bigint AS lateness_eligible_orders,
COUNT(*) FILTER (WHERE is_late IS TRUE)::bigint AS late_orders,
COUNT(*) FILTER (WHERE duration_eligible)::bigint AS duration_eligible_orders,
COUNT(*) FILTER (WHERE effective_delivery_time IS NULL)::bigint AS missing_actual,
COUNT(*) FILTER (WHERE promised_delivery_time IS NULL)::bigint AS missing_estimated,
COUNT(*) FILTER (WHERE order_purchase_time IS NULL)::bigint AS missing_purchase,
COUNT(*) FILTER (WHERE duration_eligible AND (delivery_days IS NULL OR delivery_days < 0))::bigint AS invalid_duration,
COUNT(*) FILTER (WHERE (lateness_eligible IS DISTINCT FROM (effective_delivery_time IS NOT NULL AND promised_delivery_time IS NOT NULL)) OR (lateness_eligible AND is_late IS DISTINCT FROM (effective_delivery_time > promised_delivery_time)) OR (NOT lateness_eligible AND is_late IS NOT NULL))::bigint AS invalid_late_flags,
AVG(delivery_days) FILTER (WHERE duration_eligible) AS mean_delivery_days,
(100.0 * COUNT(*) FILTER (WHERE is_late IS TRUE) / NULLIF(COUNT(*) FILTER (WHERE lateness_eligible),0)) AS late_rate_pct,
(100.0 * COUNT(*) FILTER (WHERE lateness_eligible) / NULLIF(COUNT(*),0)) AS lateness_coverage_pct
FROM {SOURCE}
WHERE order_purchase_time >= DATE '{start}' AND order_purchase_time < DATE '{end}'"""
    return {'metric_id':metric_id,'start':start,'end':end,'source':SOURCE,'sql':sql,'policy':POLICY,'time_basis':'order_purchase_time','max_rows':1,'causal_claim':False}

def _count(row,key):
    v=row.get(key)
    if type(v) is int: n=v
    elif isinstance(v,str) and re.fullmatch(r'\d+',v): n=int(v)
    else: raise DeliveryRejected('Invalid count '+key)
    if n<0:raise DeliveryRejected('Negative count '+key)
    return n

def _decimal(row,key,nullable=False):
    v=row.get(key)
    if v is None:
        if nullable:return None
        raise DeliveryRejected('Null decimal '+key)
    if isinstance(v,bool):raise DeliveryRejected('Boolean decimal '+key)
    try: d=Decimal(str(v))
    except (InvalidOperation,ValueError):raise DeliveryRejected('Invalid decimal '+key)
    if not d.is_finite():raise DeliveryRejected('Nonfinite decimal '+key)
    return d

@retain_validated
def validate_metric(plan,response):
    if not isinstance(plan,dict):raise DeliveryRejected('Untrusted plan')
    try: expected=compile_metric(plan['metric_id'],plan['start'],plan['end'])
    except (KeyError,TypeError) as e:raise DeliveryRejected('Invalid plan') from e
    if plan!=expected: raise DeliveryRejected('Tampered plan')
    if not isinstance(response,dict) or not isinstance(response.get('rows'),list) or len(response['rows'])!=1 or not isinstance(response['rows'][0],dict):raise DeliveryRejected('Expected one aggregate row')
    row=response['rows'][0]
    keys=('eligible_orders','distinct_orders','lateness_eligible_orders','late_orders','duration_eligible_orders','missing_actual','missing_estimated','missing_purchase','invalid_duration','invalid_late_flags')
    c={k:_count(row,k) for k in keys}
    total=c['eligible_orders']; lateeligible=c['lateness_eligible_orders']; late=c['late_orders']; duration=c['duration_eligible_orders']
    if total==0:raise DeliveryRejected('NO_SOURCE_COVERAGE')
    if c['distinct_orders']!=total or not 0<=late<=lateeligible<=total or duration>total:raise DeliveryRejected('Grain or denominator mismatch')
    if c['missing_actual']>total or c['missing_estimated']>total or c['missing_purchase']>total or lateeligible>total-c['missing_actual'] or lateeligible>total-c['missing_estimated'] or duration>total-c['missing_actual'] or duration>total-c['missing_purchase']: raise DeliveryRejected('Missing evidence population mismatch')
    if c['missing_purchase']!=0:raise DeliveryRejected('Unattributed purchase records')
    if c['invalid_duration'] or c['invalid_late_flags']:raise DeliveryRejected('Invalid delivery flags/duration')
    avg=_decimal(row,'mean_delivery_days',True); rate=_decimal(row,'late_rate_pct',True); coverage=_decimal(row,'lateness_coverage_pct')
    tol=Decimal('0.00001')
    if not 0<=coverage<=100 or abs(coverage-100*Decimal(lateeligible)/total)>tol:raise DeliveryRejected('Coverage mismatch')
    if lateeligible:
        if rate is None or not 0<=rate<=100 or abs(rate-100*Decimal(late)/lateeligible)>tol:raise DeliveryRejected('Late rate mismatch')
    elif rate is not None or late:raise DeliveryRejected('Invalid empty lateness population')
    if duration:
        if avg is None or avg<0:raise DeliveryRejected('Invalid mean duration')
    elif avg is not None:raise DeliveryRejected('Invalid empty duration population')
    values={'late_delivery_rate':rate,'average_delivery_days':avg,'delivered_order_count':Decimal(duration),'delivery_evidence_coverage':coverage}
    value=values[plan['metric_id']]
    if value is None:raise DeliveryRejected('INSUFFICIENT_DELIVERY_EVIDENCE')
    return {'status':'MEASURED_WITH_SCOPE_LIMITS','metric_id':plan['metric_id'],'value':str(value),'unit':METRICS[plan['metric_id']][1],'source':SOURCE,'period':[plan['start'],plan['end']],'population':{k:v for k,v in c.items() if k not in ('distinct_orders','invalid_duration','invalid_late_flags')},'policy':POLICY,'time_basis':'order_purchase_time','causal_claim':False,'limitations':['Purchase-time cohorts; not delivery-completion cohorts','Actual delivery dates may include modeled incident adjustments','Orders missing delivery timestamps are excluded from lateness denominator','Nonempty period is not certification of continuous coverage','Descriptive; no causal inference']}

async def measure(metric_id,start,end,reader):
    plan=compile_metric(metric_id,start,end)
    row=await reader(plan['sql'],'4C15 governed delivery metric '+metric_id)
    return validate_metric(plan,{'rows':[row]})
