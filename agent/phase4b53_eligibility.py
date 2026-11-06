"""Observed financial population validation, not a general recognition policy.
This is an additive diagnostic. It never grants metric or join execution permission.
"""
from __future__ import annotations
from dataclasses import dataclass
from datetime import date
from decimal import Decimal, InvalidOperation

@dataclass(frozen=True)
class Period:
    start: str
    end: str
    def __post_init__(self):
        try: a,b = date.fromisoformat(self.start),date.fromisoformat(self.end)
        except (TypeError,ValueError): raise ValueError('INVALID_DATE') from None
        if a>=b: raise ValueError('INVALID_PERIOD')

def time_filter(alias, name, p):
    if (alias,name) not in {('o','order_purchase_timestamp'),('e','order_purchase_timestamp'),('d','business_date')}:
        raise ValueError('UNAPPROVED_DATE_FIELD')
    raw=f'NULLIF(BTRIM({alias}."{name}"::text), \'\')'
    val=f"(CASE WHEN pg_input_is_valid({raw}, 'timestamp without time zone') THEN {raw}::timestamp ELSE NULL END)"
    return f"{val} >= DATE '{p.start}' AND {val} < DATE '{p.end}'"

def queries(p):
    op=time_filter('o','order_purchase_timestamp',p)
    ep=time_filter('e','order_purchase_timestamp',p)
    dp=time_filter('d','business_date',p)
    # Compute DISTINCT item order IDs once. Avoid repeated per-row correlated EXISTS scans.
    # Derived source has one row per order_id; prevents item-grain fanout.
    item_orders = '(SELECT DISTINCT order_id FROM "commerce"."order_items")'
    has_item = 'i.order_id IS NOT NULL'
    in_finance = 'e.order_id IS NOT NULL'
    missing = 'e.order_id IS NULL'
    cohort=f'''SELECT COUNT(*) AS placed, COUNT(DISTINCT o.order_id) AS placed_distinct,
       COUNT(*) FILTER(WHERE {has_item}) AS with_items,
       COUNT(*) FILTER(WHERE NOT {has_item}) AS without_items,
       COUNT(*) FILTER(WHERE {in_finance}) AS represented,
       COUNT(*) FILTER(WHERE {has_item} AND {missing}) AS item_missing_finance,
       COUNT(*) FILTER(WHERE NOT {has_item} AND {in_finance}) AS finance_missing_item,
       COUNT(*) FILTER(WHERE {missing} AND o.order_status='canceled') AS canceled_missing,
       COUNT(*) FILTER(WHERE {missing} AND o.order_status='unavailable') AS unavailable_missing,
       COUNT(*) FILTER(WHERE {missing} AND o.order_status='created') AS created_missing,
       COUNT(*) FILTER(WHERE {missing} AND o.order_status NOT IN ('canceled','unavailable','created')) AS other_missing,
       COUNT(*) FILTER(WHERE {missing} AND o.order_status IS NULL) AS null_status_missing
       FROM "commerce"."orders" o
       LEFT JOIN {item_orders} i ON i.order_id=o.order_id
       LEFT JOIN "semantic"."order_economics" e ON e.order_id=o.order_id
       WHERE {op} LIMIT 1'''
    finance=f'''SELECT COUNT(*) AS rows, COUNT(DISTINCT e.order_id) AS unique_orders,
      SUM(e.effective_revenue) AS revenue, SUM(e.effective_cogs) AS cogs,
      SUM(e.effective_contribution_profit) AS profit
      FROM "semantic"."order_economics" e WHERE {ep} LIMIT 1'''
    daily=f'''SELECT COUNT(*) AS days, SUM(d.revenue) AS revenue, SUM(d.cogs) AS cogs,
      SUM(d.contribution_profit) AS profit, SUM(d.orders) AS orders
      FROM "semantic"."daily_commerce" d WHERE {dp} LIMIT 1'''
    integrity=f'''SELECT COUNT(*) AS financial_rows,
      COUNT(*) FILTER(WHERE o.order_id IS NULL) AS finance_only,
      COUNT(*) FILTER(WHERE o.order_id IS NOT NULL AND NOT ({op})) AS period_mismatch,
      COUNT(*) FILTER(WHERE i.order_id IS NULL) AS no_items
      FROM "semantic"."order_economics" e
      LEFT JOIN "commerce"."orders" o ON o.order_id=e.order_id
      LEFT JOIN {item_orders} i ON i.order_id=e.order_id
      WHERE {ep} LIMIT 1'''
    return {'cohort':cohort,'finance':finance,'daily':daily,'integrity':integrity}

def decimal(record,key):
    x=record.get(key)
    if x is None or isinstance(x,bool): raise ValueError('MISSING:'+key)
    try: v=Decimal(str(x))
    except (InvalidOperation,ValueError,TypeError): raise ValueError('INVALID:'+key) from None
    if not v.is_finite():raise ValueError('NONFINITE:'+key)
    return v

def assess(p,data,tolerance=Decimal('0.05')):
    checks=[]
    def check(name,passed,detail):checks.append({'name':name,'passed':bool(passed),'detail':detail})
    try:
        a,b,c,d=(data[k] for k in ('cohort','finance','daily','integrity'))
        if not all(isinstance(x,dict) for x in (a,b,c,d)):raise ValueError('INVALID_RESULT')
        av={k:decimal(a,k) for k in ('placed','placed_distinct','with_items','without_items','represented','item_missing_finance','finance_missing_item','canceled_missing','unavailable_missing','created_missing','other_missing','null_status_missing')}
        frows=decimal(b,'rows');funique=decimal(b,'unique_orders');days=decimal(c,'days');dorders=decimal(c,'orders')
        check('ONE_ROW_PER_ORDER',av['placed']==av['placed_distinct'],'No order-grain fanout')
        check('ITEM_PARTITION',av['with_items']+av['without_items']==av['placed'],'All orders classified by item presence')
        check('ITEMS_EQUAL_FINANCIAL_POPULATION',av['item_missing_finance']==av['finance_missing_item']==0 and av['with_items']==av['represented'],'No order ID mismatch in either direction')
        exclusions=sum((av[k] for k in ('canceled_missing','unavailable_missing','created_missing','other_missing','null_status_missing')),Decimal(0))
        check('STATUS_BREAKDOWN_BALANCES',exclusions==av['placed']-av['represented'],'Statuses describe exclusions, not eligibility policy')
        check('FINANCE_GRAIN_MATCHES',frows==funique==av['represented'],'Finance population unique at order grain')
        check('PERIOD_AND_ITEM_INTEGRITY',decimal(d,'financial_rows')==frows and all(decimal(d,k)==0 for k in ('finance_only','period_mismatch','no_items')),'No unmatched finance IDs, wrong dates, or finance without items')
        check('COVERAGE',av['placed']>0 and frows>0 and days>0,'Nonempty source coverage')
        for metric in ('revenue','cogs','profit'):
            x,y=decimal(b,metric),decimal(c,metric)
            check('DAILY_'+metric.upper(),abs(x-y)<=tolerance,f'Difference {abs(x-y)}; tolerance {tolerance}')
        check('DAILY_ORDER_POPULATION',dorders==funique,'Daily order count refers to financial population')
        revenue=decimal(b,'revenue');cogs=decimal(b,'cogs');profit=decimal(b,'profit')
        check('VALID_MARGIN_DENOMINATOR',revenue!=0,'Ratios use summed financial revenue as denominator')
        ok=all(x['passed'] for x in checks)
        return {'period':[p.start,p.end],'status':'RECONCILED_FOR_REVIEW' if ok else 'DISCREPANCIES_FOUND','checks':checks,
            'measurements':{'placed_orders':int(av['placed']),'orders_with_items':int(av['with_items']),'orders_without_items':int(av['without_items']),'financial_orders':int(funique),
            'excluded_statuses':{k:int(av[k]) for k in ('canceled_missing','unavailable_missing','created_missing','other_missing','null_status_missing')},
            'effective_revenue':float(revenue),'effective_cogs':float(cogs),'effective_contribution_profit':float(profit),
            'effective_gross_margin_pct':float(100*(revenue-cogs)/revenue) if revenue else None,
            'effective_contribution_margin_pct':float(100*profit/revenue) if revenue else None},'execution_approved':False}
    except (KeyError,ValueError) as exc:
        return {'period':[p.start,p.end],'status':'INCONCLUSIVE','issues':[str(exc)],'checks':checks,'execution_approved':False}

def summarize(rows):
    return {'phase':'4B.5.3','status':'REVIEW_ELIGIBLE' if rows and all(r['status']=='RECONCILED_FOR_REVIEW' for r in rows) else 'REVIEW_BLOCKED',
        'periods':rows,'execution_approved':False,
        'provenance':{'population':'Observed: finance rows correspond to commerce orders with >=1 order item. Traced to build_order_profitability(); not a general accounting recognition policy.',
                      'base_revenue':'Sum of observed order-item prices','cogs':'Modeled unit costs from generated cost history',
                      'profit':'Derived using modeled fulfillment/processing/marketing/incentive costs and refunds',
                      'effective_adjustments':'Regional revenue multiplier and INC006 incremental revenue, COGS, marketing, incentives',
                      'agent_boundary':'Only commerce and approved semantic sources; staging forbidden for agent runtime'},
        'disclaimer':'Read-only reconciliation, not accounting certification or independent causal evidence. No new metric/dimension/join approval.'}
