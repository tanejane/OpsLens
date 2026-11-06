"""Purchase-cohort returns and exclusive-seller refund concentration."""
from decimal import Decimal, InvalidOperation
from agent.phase4c15_delivery import period, _count, DeliveryRejected
from agent.investigation_result import retain_validated

COUNTS=('orders','returned_orders','refunded_orders','events')
LIMITS=['Returns are recorded synthetic outcomes; this is descriptive, not causal evidence.',
 'Purchase cohorts include all recorded linked return events at the dataset snapshot, including events after purchase-period end; this is not a refund-date cash-flow metric.',
 'No recorded return is not proof of no return; observation windows differ across purchase cohorts.',
 'Multi-seller and missing seller mappings are separate; refunds are never allocated to an item, SKU or shared seller.',
 'Multiple distinct return events are summed once per event ID, then joined once per order. Refunds are not reconciled to modeled finance adjustments.']

def compile_plan(start,end,detail=False):
 start,end=period(start,end)
 purchase_time="CASE WHEN pg_input_is_valid(order_purchase_timestamp::text, 'timestamp without time zone') THEN order_purchase_timestamp::timestamp END"
 base=f"""WITH base AS (
 SELECT order_id,COUNT(*) AS n FROM commerce.orders
 WHERE ({purchase_time}) >= DATE '{start}' AND ({purchase_time}) < DATE '{end}' GROUP BY order_id
 ), events AS (
 SELECT r.* FROM cx.returns r JOIN base b ON r.order_id=b.order_id
 ), r AS (
 SELECT order_id,COUNT(*) AS events,SUM(refund_amount::numeric) AS amount FROM events GROUP BY order_id
 ), items AS (
 SELECT order_id,COUNT(DISTINCT order_item_id) AS item_rows,COUNT(DISTINCT seller_id) AS sellers,MIN(seller_id) AS seller,
 COUNT(*) FILTER(WHERE seller_id IS NULL OR BTRIM(seller_id)='') AS missing FROM commerce.order_items GROUP BY order_id
 ), joined AS (
 SELECT b.order_id,b.n,COALESCE(r.events,0) AS events,COALESCE(r.amount,0) AS amount,
 COALESCE(i.item_rows,0) AS item_rows,i.seller,
 CASE WHEN i.order_id IS NULL OR i.missing>0 OR i.sellers=0 THEN 'unknown'
 WHEN i.sellers>1 THEN 'multi_seller' ELSE 'single_seller' END AS bucket
 FROM base b LEFT JOIN r ON b.order_id=r.order_id LEFT JOIN items i ON b.order_id=i.order_id
 )"""
 # The initial measurement does not query item attribution.
 if not detail:
  base=base[:base.index(', items AS')]+", joined AS (SELECT b.order_id,b.n,COALESCE(r.events,0) AS events,COALESCE(r.amount,0) AS amount FROM base b LEFT JOIN r ON b.order_id=r.order_id)"
 agg="COUNT(*) AS orders,COUNT(*) FILTER(WHERE events>0) AS returned_orders,COUNT(*) FILTER(WHERE amount>0) AS refunded_orders,COALESCE(SUM(events),0) AS events,COALESCE(SUM(amount),0)::text AS refund_amount"
 audit="""(SELECT COUNT(*) FROM base WHERE n<>1 OR order_id IS NULL OR BTRIM(order_id)='') AS invalid_orders,
 (SELECT COUNT(*) FROM events WHERE return_id IS NULL OR BTRIM(return_id)='' OR refund_amount IS NULL OR refund_amount::text IN ('NaN','Infinity','-Infinity') OR refund_amount<0) AS invalid_events,
 (SELECT COUNT(*) FROM events WHERE return_id IN (SELECT return_id FROM cx.returns GROUP BY return_id HAVING COUNT(*)>1)) AS duplicate_events"""
 if detail:
  audit+=",(SELECT COUNT(*)-COUNT(DISTINCT (i.order_id,i.order_item_id))+COUNT(*) FILTER(WHERE i.order_item_id IS NULL) FROM commerce.order_items i JOIN base b ON i.order_id=b.order_id) AS invalid_items"
  sql=base+f", buckets AS (SELECT bucket,{agg},COUNT(*) FILTER(WHERE item_rows>1) AS multi_item_orders FROM joined GROUP BY bucket), sellers AS (SELECT seller,{agg},COUNT(*) FILTER(WHERE item_rows>1) AS multi_item_orders FROM joined WHERE bucket='single_seller' GROUP BY seller) SELECT {audit},COALESCE((SELECT jsonb_agg(to_jsonb(buckets)) FROM buckets),'[]'::jsonb) AS buckets,COALESCE((SELECT jsonb_agg(to_jsonb(sellers)) FROM sellers),'[]'::jsonb) AS sellers"
 else:
  sql=base+f" SELECT {agg},{audit},(SELECT COUNT(*) FROM cx.returns x WHERE x.order_id IS NULL OR NOT EXISTS(SELECT 1 FROM commerce.orders o WHERE o.order_id=x.order_id)) AS source_unlinked_events,(SELECT jsonb_agg(DISTINCT source_type) FROM events) AS source_types FROM joined"
 return {'start':start,'end':end,'detail':detail,'sql':sql}

def measures(row):
 c={k:_count(row,k) for k in COUNTS}
 try:amount=Decimal(str(row['refund_amount']))
 except (InvalidOperation,KeyError):raise DeliveryRejected('Invalid refund amount')
 if not amount.is_finite() or amount<0 or not 0<=c['refunded_orders']<=c['returned_orders']<=c['orders'] or c['events']<c['returned_orders']:
  raise DeliveryRejected('Refund denominator mismatch')
 if (amount>0)!=(c['refunded_orders']>0) or (c['events']>0)!=(c['returned_orders']>0):raise DeliveryRejected('Refund amount/count mismatch')
 return {**c,'refund_amount':str(amount),'return_rate_pct':str(Decimal(100)*c['returned_orders']/c['orders']) if c['orders'] else None,
  'refund_rate_pct':str(Decimal(100)*c['refunded_orders']/c['orders']) if c['orders'] else None}

def audit(plan,row):
 if plan!=compile_plan(plan['start'],plan['end'],plan['detail']):raise DeliveryRejected('Tampered refund plan')
 if any(_count(row,k) for k in ('invalid_orders','invalid_events','duplicate_events')):raise DeliveryRejected('Invalid or duplicated order/return identifiers or amounts')

@retain_validated
def validate_initial(plan,row):
 audit(plan,row)
 if plan['detail']:raise DeliveryRejected('Expected summary plan')
 return {'evidence_id':f"returns:{plan['start']}:{plan['end']}",'period':[plan['start'],plan['end']],
  'source':'commerce.orders + cx.returns','refund_amount_unit':'source_currency_unspecified','population':measures(row),
  'source_unlinked_events':_count(row,'source_unlinked_events'),'source_types':row.get('source_types') or [],
  'limitations':LIMITS,'causal_claim':False}

@retain_validated
def validate_detail(plan,row,initial):
 audit(plan,row)
 if _count(row,'invalid_items'):raise DeliveryRejected('Invalid or duplicated order-item identifiers')
 if not plan['detail'] or initial['period']!=[plan['start'],plan['end']] or initial['source']!='commerce.orders + cx.returns':raise DeliveryRejected('Refund scope mismatch')
 def group(raw):
  c=measures(raw);multi=_count(raw,'multi_item_orders')
  if multi>c['orders']:raise DeliveryRejected('Multi-item denominator mismatch')
  return {**c,'multi_item_orders':multi}
 buckets={}
 for raw in row['buckets']:
  key=raw.get('bucket')
  if key not in ('single_seller','multi_seller','unknown') or key in buckets:raise DeliveryRejected('Invalid refund partition')
  buckets[key]=group(raw)
 def reconcile(rows,expected):
  if any(sum(Decimal(str(r[k])) for r in rows)!=Decimal(str(expected[k])) for k in (*COUNTS,'refund_amount')):raise DeliveryRejected('Refund reconciliation failed')
 reconcile(list(buckets.values()),initial['population'])
 if not isinstance(row['sellers'],list) or len(row['sellers'])>5000:raise DeliveryRejected('Seller bound exceeded')
 sellers=[];seen=set();total=Decimal(initial['population']['refund_amount'])
 for raw in row['sellers']:
  seller=raw.get('seller')
  if not isinstance(seller,str) or not seller.strip() or len(seller)>128 or seller in seen:raise DeliveryRejected('Invalid seller identifier')
  seen.add(seller);c=group(raw)
  sellers.append({'seller_id':seller,**c,'share_of_all_refunds_pct':str(100*Decimal(c['refund_amount'])/total) if total else None})
 zero={k:0 for k in (*COUNTS,'refund_amount','multi_item_orders')}
 single=buckets.get('single_seller',zero)
 reconcile(sellers,single)
 if sum(s['multi_item_orders'] for s in sellers)!=single['multi_item_orders']:raise DeliveryRejected('Multi-item reconciliation failed')
 sellers.sort(key=lambda s:(-Decimal(s['refund_amount']),-s['returned_orders'],s['seller_id']))
 return {'evidence_id':f"refund-concentration:{plan['start']}:{plan['end']}",'period':initial['period'],
  'source':'commerce.orders + cx.returns + commerce.order_items','population':initial['population'],
  'buckets':buckets,'sellers':sellers,'limitations':LIMITS,'causal_claim':False,
  'methodology':'Aggregate unique return events by order before joining purchase orders; aggregate item sellers before attribution. Return rate = orders with recorded returns / purchased orders. Refund share = seller-cohort refund amount / all linked cohort refund amount, including shared and unknown attribution.'}

async def initial(start,end,reader):
 plan=compile_plan(start,end);evidence=validate_initial(plan,await reader(plan['sql'],'Governed order-linked refund summary'))
 p=evidence['population']
 return {'route':'refund_concentration','status':'MEASURED_WITH_LIMITATIONS','executable':True,'causal_claim':False,
  'refund_intent':True,'evidence':evidence,'limitations':LIMITS,
  'reason':f"{p['returned_orders']} of {p['orders']} purchased orders have recorded returns ({p['events']} return events); linked refunds total {p['refund_amount']}."}

async def analyze(evidence,reader):
 plan=compile_plan(*evidence['period'],detail=True)
 return validate_detail(plan,await reader(plan['sql'],'Governed exclusive-seller refund concentration'),evidence)
