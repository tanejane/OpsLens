"""Fixed read-only order-cohort comparison. Model text never becomes SQL."""
from decimal import Decimal
from agent.phase4c15_delivery import period, _count, _decimal, DeliveryRejected
from agent.investigation_result import retain_validated

def compile_comparison(start,end):
    start,end=period(start,end)
    # Aggregate each source by ID before joining; reject duplicate source IDs
    # instead of silently selecting one conflicting observation.
    sql=f"""WITH d AS (
 SELECT order_id, COUNT(*) AS n, MIN(order_purchase_time) AS purchased,
 MIN(effective_delivery_time) AS actual, MIN(promised_delivery_time) AS promised
 FROM semantic.order_delivery_evidence_v1
 WHERE order_purchase_time >= DATE '{start}' AND order_purchase_time < DATE '{end}' GROUP BY order_id
), r AS (
 SELECT order_id, COUNT(*) AS n, MIN(purchase_time) AS purchased,
 MIN(order_score) AS score, MAX(review_records) AS records
 FROM semantic.order_review_evidence_v1 GROUP BY order_id
), joined AS (
 SELECT d.*, r.n AS rn, r.purchased AS rpurchased, r.score, r.records,
 CASE WHEN actual IS NULL OR promised IS NULL THEN 'unclassified'
 WHEN actual > promised THEN 'late' ELSE 'on_time' END AS cohort
 FROM d LEFT JOIN r ON d.order_id=r.order_id
), grouped AS (
 SELECT cohort, COUNT(*) AS orders, COUNT(score) AS reviewed,
 COUNT(*) FILTER (WHERE score <= 2) AS low,
 COALESCE(SUM(score),0) AS score_sum,
 COUNT(*) FILTER (WHERE records > 1) AS multi_review_orders
 FROM joined GROUP BY cohort
)
SELECT (SELECT COUNT(*) FROM joined) AS total,
 (SELECT COUNT(*) FROM joined WHERE n <> 1 OR rn > 1 OR order_id IS NULL) AS invalid_grain,
 (SELECT COUNT(*) FROM joined WHERE rn IS NOT NULL AND purchased IS DISTINCT FROM rpurchased) AS misaligned,
 (SELECT COUNT(*) FROM joined WHERE score < 1 OR score > 5) AS invalid_scores,
 (SELECT COUNT(*) FROM joined WHERE rn IS NULL) AS missing_review_rows,
 COALESCE((SELECT jsonb_agg(to_jsonb(grouped)) FROM grouped),'[]'::jsonb) AS cohorts"""
    return {'start':start,'end':end,'sql':sql,'sources':['semantic.order_delivery_evidence_v1','semantic.order_review_evidence_v1']}

@retain_validated
def validate(plan,row):
    if plan != compile_comparison(plan['start'],plan['end']): raise DeliveryRejected('Tampered comparison plan')
    total=_count(row,'total')
    if any(_count(row,k) for k in ('invalid_grain','misaligned','invalid_scores')): raise DeliveryRejected('Invalid order grain, period alignment or score')
    missing=_count(row,'missing_review_rows')
    if missing>total: raise DeliveryRejected('Missingness exceeds population')
    groups={}
    if not isinstance(row.get('cohorts'),list): raise DeliveryRejected('Missing cohorts')
    for raw in row['cohorts']:
        name=raw.get('cohort')
        if name not in ('late','on_time','unclassified') or name in groups: raise DeliveryRejected('Overlapping cohorts')
        n=_count(raw,'orders'); reviewed=_count(raw,'reviewed'); low=_count(raw,'low'); multi=_count(raw,'multi_review_orders')
        score=_decimal(raw,'score_sum')
        if not 0<=low<=reviewed<=n or multi>n or not Decimal(reviewed)<=score<=5*reviewed: raise DeliveryRejected('Cohort reconciliation failed')
        if score > 2*low+5*(reviewed-low) or score < low+2*(reviewed-low): raise DeliveryRejected('Low-rating counts contradict score sum')
        groups[name]={**raw,'average_score':str(score/reviewed) if reviewed else None,
            'low_rating_rate_pct':str(100*Decimal(low)/reviewed) if reviewed else None,
            'review_coverage_pct':str(100*Decimal(reviewed)/n) if n else None,'missing_reviews':n-reviewed}
    if sum(_count(g,'orders') for g in groups.values())!=total: raise DeliveryRejected('Population reconciliation failed')
    a=groups.get('late',{}).get('average_score'); b=groups.get('on_time',{}).get('average_score')
    difference=str(Decimal(a)-Decimal(b)) if a is not None and b is not None else None
    return {'evidence_id':'delivery-review:'+plan['start']+':'+plan['end'],
        'period':[plan['start'],plan['end']],'sources':plan['sources'],'cohorts':groups,
        'validation':{key:row[key] for key in ('invalid_grain','misaligned','invalid_scores')},
        'total_orders':total,'missing_review_rows':missing,'late_minus_on_time_score':difference,
        'methodology':'Left join by unique order ID. Purchase-time cohort; late means actual > promised. Each order score is the mean of its non-null effective reviews. Low rating means order score <= 2.',
        'limitations':['Descriptive association, not a causal effect.','Missing delivery dates form an unclassified cohort; missing reviews are excluded from rating denominators.','Effective delivery dates and review scores may include modeled incident adjustments.','Review respondents may differ from orders without reviews.'],
        'causal_claim':False}

async def investigate(start,end,reader):
    plan=compile_comparison(start,end)
    evidence=validate(plan,await reader(plan['sql'],'Governed late versus on-time review comparison'))
    difference=evidence['late_minus_on_time_score']
    reason=(f'Late orders averaged {difference} rating points relative to on-time orders among reviewed orders.' if difference is not None else 'Available cohort counts are retained; both cohorts need reviews to estimate a rating difference.')
    return {'route':'delivery_review_comparison','status':'MEASURED_WITH_LIMITATIONS','executable':True,'causal_claim':False,
        'reason':reason,'evidence':evidence,'limitations':evidence['limitations'],
        'next_steps':['Compare review coverage before interpreting the rating difference.','Repeat this comparison in another purchase month to assess whether the pattern persists.']}
