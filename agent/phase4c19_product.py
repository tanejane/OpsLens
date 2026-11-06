"""Governed product/category descriptive metrics; requires separately approved view access."""
from agent.investigation_result import retain_validated
from datetime import date
from decimal import Decimal, InvalidOperation
import re

SOURCE='semantic.order_item_product_evidence_v1'
POLICY='item_grain_price_excludes_freight_unknown_category_retained'
METRICS={'category_order_count':'orders','units_sold':'units','item_gmv':'money','average_item_price':'money_per_unit','category_gmv_share':'percent'}
class ProductRejected(ValueError): pass

def compile_metric(metric_id,start,end,category):
    if type(metric_id) is not str or metric_id not in METRICS: raise ProductRejected('Unregistered metric')
    if type(start) is not str or type(end) is not str or not re.fullmatch(r'\d{4}-\d{2}-\d{2}',start) or not re.fullmatch(r'\d{4}-\d{2}-\d{2}',end):raise ProductRejected('Invalid ISO dates')
    try:a,b=date.fromisoformat(start),date.fromisoformat(end)
    except ValueError as e:raise ProductRejected('Invalid date') from e
    if a>=b or (b-a).days>366:raise ProductRejected('Invalid interval')
    if type(category) is not str or not 1<=len(category)<=100 or not re.fullmatch(r'[a-zA-Z0-9_]+',category):raise ProductRejected('Unsafe category slug')
    # MCP policy requires every actual relation reference to be schema-qualified.
    # Use independent derived aggregates rather than named CTE references,
    # which the policy can otherwise misidentify as unqualified relations.
    filtered=(f"FROM {SOURCE} WHERE order_purchase_time >= DATE '{start}' "
              f"AND order_purchase_time < DATE '{end}'")
    sql=f"""SELECT totals.*, selected.*
FROM (
 SELECT COUNT(*)::bigint total_units,
        COUNT(DISTINCT (order_id,order_item_id))::bigint unique_items,
        COUNT(DISTINCT order_id)::bigint total_orders,
        COALESCE(SUM(item_price),0)::numeric total_gmv,
        COUNT(*) FILTER (WHERE item_price IS NULL OR item_price < 0 OR freight_value IS NULL OR freight_value < 0)::bigint invalid_items
 {filtered}
) AS totals
CROSS JOIN (
 SELECT COUNT(*)::bigint category_units,
        COUNT(DISTINCT (order_id,order_item_id))::bigint category_unique_items,
        COUNT(DISTINCT order_id)::bigint category_orders,
        COALESCE(SUM(item_price),0)::numeric category_gmv,
        COUNT(*) FILTER (WHERE item_price IS NULL OR item_price < 0 OR freight_value IS NULL OR freight_value < 0)::bigint category_invalid_items
 {filtered} AND category='{category}'
) AS selected"""
    return {'metric_id':metric_id,'start':start,'end':end,'category':category,'source':SOURCE,'sql':sql,'policy':POLICY,'time_basis':'order_purchase_time','max_rows':1,'causal_claim':False}

def _count(row,k):
    v=row.get(k)
    if type(v) is int and v>=0:return v
    if isinstance(v,str) and re.fullmatch(r'\d+',v):return int(v)
    raise ProductRejected('Invalid count '+k)

def _num(row,k):
    v=row.get(k)
    if type(v) is bool or v is None:raise ProductRejected('Invalid numeric '+k)
    try:d=Decimal(str(v))
    except (ValueError,InvalidOperation) as e:raise ProductRejected('Invalid numeric '+k) from e
    if not d.is_finite():raise ProductRejected('Non-finite '+k)
    return d

@retain_validated
def validate_metric(plan,response):
    if type(plan) is not dict:raise ProductRejected('Invalid plan')
    try:expected=compile_metric(plan['metric_id'],plan['start'],plan['end'],plan['category'])
    except (KeyError,TypeError) as e:raise ProductRejected('Invalid plan') from e
    if plan!=expected:raise ProductRejected('Plan tampering')
    if type(response) is not dict or type(response.get('rows')) is not list or len(response['rows'])!=1 or type(response['rows'][0]) is not dict:raise ProductRejected('Expected one row')
    r=response['rows'][0]
    c={k:_count(r,k) for k in ('total_units','unique_items','total_orders','invalid_items','category_units','category_unique_items','category_orders','category_invalid_items')}
    if c['total_units']==0:raise ProductRejected('NO_SOURCE_COVERAGE')
    if c['unique_items']!=c['total_units'] or c['category_unique_items']!=c['category_units']:raise ProductRejected('Duplicate item keys')
    if not 0<=c['category_units']<=c['total_units'] or not 0<=c['category_orders']<=min(c['total_orders'],c['category_units']) or c['total_orders']>c['total_units']:raise ProductRejected('Invalid population')
    if c['invalid_items'] or c['category_invalid_items']:raise ProductRejected('Invalid source prices')
    total,selected=_num(r,'total_gmv'),_num(r,'category_gmv')
    if total<0 or selected<0 or selected>total+Decimal('0.00001'):raise ProductRejected('GMV mismatch')
    if c['category_units']==0 and selected!=0:raise ProductRejected('Empty category GMV mismatch')
    vals={'category_order_count':Decimal(c['category_orders']),'units_sold':Decimal(c['category_units']),'item_gmv':selected,
          'average_item_price':selected/c['category_units'] if c['category_units'] else None,
          'category_gmv_share':100*selected/total if total else None}
    val=vals[plan['metric_id']]
    if val is None:raise ProductRejected('INSUFFICIENT_DENOMINATOR')
    return {'status':'MEASURED_WITH_SCOPE_LIMITS','metric_id':plan['metric_id'],'category':plan['category'],'value':str(val),'unit':METRICS[plan['metric_id']], 'period':[plan['start'],plan['end']], 'source':SOURCE,'time_basis':'order_purchase_time','policy':POLICY,'population':c,'total_item_gmv':str(total),'category_item_gmv':str(selected),'causal_claim':False,'limitations':['Item units are order-item rows, not inventory units','Item GMV excludes freight and is not audited financial revenue','Unknown categories are retained in the denominator','Category order counts are distinct only within the category and cannot be summed across categories','No stockout or causal conclusions','Period completeness not independently certified']}

async def measure(metric_id,start,end,category,reader):
    plan=compile_metric(metric_id,start,end,category)
    row=await reader(plan['sql'],'4C19 governed product metric '+metric_id)
    return validate_metric(plan,{'rows':[row]})
