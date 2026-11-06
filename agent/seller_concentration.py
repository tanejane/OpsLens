"""Exclusive single-seller order cohorts; no allocation of shared orders."""
from decimal import Decimal
from agent.phase4c15_delivery import period, _count, DeliveryRejected, measure as delivery_measure
from agent.investigation_result import retain_validated

def compile_plan(start,end):
    start,end=period(start,end)
    sql=f"""WITH d AS (
 SELECT order_id, COUNT(*) AS n, BOOL_OR(lateness_eligible) AS eligible, BOOL_OR(is_late) AS late
 FROM semantic.order_delivery_evidence_v1
 WHERE order_purchase_time >= DATE '{start}' AND order_purchase_time < DATE '{end}' GROUP BY order_id
), items AS (
 SELECT order_id, COUNT(DISTINCT seller_id) AS sellers, MIN(seller_id) AS seller,
 COUNT(*) FILTER (WHERE seller_id IS NULL) AS missing
 FROM commerce.order_items GROUP BY order_id
), joined AS (
 SELECT d.*, i.seller,
 CASE WHEN i.order_id IS NULL OR i.missing>0 OR i.sellers=0 THEN 'unknown'
 WHEN i.sellers>1 THEN 'multi_seller' ELSE 'single_seller' END AS bucket
 FROM d LEFT JOIN items i ON d.order_id=i.order_id
), buckets AS (
 SELECT bucket,COUNT(*) AS orders,COUNT(*) FILTER(WHERE eligible) AS eligible,
 COUNT(*) FILTER(WHERE eligible AND late) AS late FROM joined GROUP BY bucket
), sellers AS (
 SELECT seller,COUNT(*) AS orders,COUNT(*) FILTER(WHERE eligible) AS eligible,
 COUNT(*) FILTER(WHERE eligible AND late) AS late FROM joined WHERE bucket='single_seller' GROUP BY seller
)
SELECT (SELECT COUNT(*) FROM joined) AS total,
 (SELECT COUNT(*) FROM joined WHERE n<>1 OR order_id IS NULL) AS invalid_grain,
 COALESCE((SELECT jsonb_agg(to_jsonb(buckets)) FROM buckets),'[]'::jsonb) AS buckets,
 COALESCE((SELECT jsonb_agg(to_jsonb(sellers)) FROM sellers),'[]'::jsonb) AS sellers"""
    return {'start':start,'end':end,'sql':sql}

def counts(row):
    values={k:_count(row,k) for k in ('orders','eligible','late')}
    if not 0<=values['late']<=values['eligible']<=values['orders']:raise DeliveryRejected('Seller denominator mismatch')
    return values

@retain_validated
def validate(plan,row,initial):
    if plan!=compile_plan(plan['start'],plan['end']):raise DeliveryRejected('Tampered seller plan')
    if _count(row,'invalid_grain'):raise DeliveryRejected('Duplicate delivery order IDs')
    buckets={}
    for raw in row['buckets']:
        key=raw.get('bucket')
        if key not in ('single_seller','multi_seller','unknown') or key in buckets:raise DeliveryRejected('Invalid attribution partition')
        buckets[key]=counts(raw)
    total=_count(row,'total')
    pop=initial['population']
    if initial['period']!=[plan['start'],plan['end']] or initial.get('source')!='semantic.order_delivery_evidence_v1':raise DeliveryRejected('Initial scope mismatch')
    for key,expected in [('orders',total),('eligible',pop['lateness_eligible_orders']),('late',pop['late_orders'])]:
        if sum(b[key] for b in buckets.values())!=expected:raise DeliveryRejected('Partition does not reconcile')
    if total!=pop['eligible_orders']:raise DeliveryRejected('Population changed')
    if not isinstance(row['sellers'],list) or len(row['sellers'])>5000:raise DeliveryRejected('Seller evidence exceeds bounded capacity')
    sellers=[];seen=set();single=buckets.get('single_seller',dict(orders=0,eligible=0,late=0))
    for raw in row['sellers']:
        seller=raw.get('seller')
        if not isinstance(seller,str) or not seller or len(seller)>128 or seller in seen:raise DeliveryRejected('Invalid or repeated seller ID')
        seen.add(seller);c=counts(raw)
        sellers.append({'seller_id':seller,**c,
            'late_rate_pct':str(100*Decimal(c['late'])/c['eligible']) if c['eligible'] else None,
            'share_of_single_seller_late_pct':str(100*Decimal(c['late'])/single['late']) if single['late'] else None})
    if any(sum(s[k] for s in sellers)!=single[k] for k in ('orders','eligible','late')):raise DeliveryRejected('Seller totals do not reconcile')
    sellers.sort(key=lambda s:(-s['late'],s['seller_id']))
    return {'evidence_id':f"seller-concentration:{plan['start']}:{plan['end']}",
        'period':[plan['start'],plan['end']],'source':'semantic.order_delivery_evidence_v1 + commerce.order_items',
        'population':pop,'buckets':buckets,'sellers':sellers,'causal_claim':False,
        'methodology':'Aggregate distinct seller IDs per order before joining unique delivery orders. Rank single-seller orders by late-order count. Late rate uses only timestamp-eligible orders; concentration share uses single-seller late orders.',
        'limitations':['Multi-seller orders are reported separately and never allocated to sellers.','Missing item/seller mappings are reported as unknown.','Association is not seller responsibility or causation.','Purchase-time cohorts; effective delivery dates may include modeled incident adjustments.','Seller IDs identify item sellers, not the party responsible for fulfillment.']}

async def initial(start,end,reader):
    evidence=await delivery_measure('late_delivery_rate',start,end,reader)
    return {'route':'seller_concentration','status':'MEASURED_WITH_LIMITATIONS','executable':True,'causal_claim':False,
        'seller_intent':True,'evidence':evidence,'reason':f"{evidence['population']['late_orders']} eligible orders arrived late.",
        'limitations':evidence['limitations']}

async def analyze(initial_evidence,reader):
    plan=compile_plan(*initial_evidence['period'])
    return validate(plan,await reader(plan['sql'],'Governed single-seller delivery concentration'),initial_evidence)
