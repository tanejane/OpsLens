"""Finance-only governed execution candidate. No LLM SQL or join permission.

The gate requires evidence from the local, read-only Phase 4B.5.3 reconciliation.
This does not change or overwrite approvals in earlier planners.
"""
from __future__ import annotations
from dataclasses import dataclass
from datetime import date
from decimal import Decimal, InvalidOperation
from pathlib import Path
import json
from agent.phase4b43_graph_planner import date_expr, require_date_pair

class FinanceGateError(ValueError): pass

# Explicit *single-source* definitions; metric selection cannot modify SQL fragments.
METRICS = {
    'placed_orders': ('commerce.orders', 'order_purchase_timestamp', 'COUNT(DISTINCT t0."order_id")', 'count'),
    'financially_represented_orders': ('semantic.order_economics','order_purchase_timestamp','COUNT(DISTINCT t0."order_id")','count'),
    'effective_revenue': ('semantic.order_economics','order_purchase_timestamp','SUM(t0."effective_revenue")','money'),
    'effective_cogs': ('semantic.order_economics','order_purchase_timestamp','SUM(t0."effective_cogs")','money'),
    'effective_contribution_profit': ('semantic.order_economics','order_purchase_timestamp','SUM(t0."effective_contribution_profit")','money'),
    'effective_gross_margin_pct': ('semantic.order_economics','order_purchase_timestamp','100.0 * (SUM(t0."effective_revenue") - SUM(t0."effective_cogs")) / NULLIF(SUM(t0."effective_revenue"),0)','percent'),
    'effective_contribution_margin_pct': ('semantic.order_economics','order_purchase_timestamp','100.0 * SUM(t0."effective_contribution_profit") / NULLIF(SUM(t0."effective_revenue"),0)','percent'),
}
FINANCE_SOURCES={'commerce.orders','semantic.order_economics'}
FINANCE_CHECKS={'ONE_ROW_PER_ORDER','ITEM_PARTITION','ITEMS_EQUAL_FINANCIAL_POPULATION',
 'STATUS_BREAKDOWN_BALANCES','FINANCE_GRAIN_MATCHES','PERIOD_AND_ITEM_INTEGRITY',
 'COVERAGE','DAILY_REVENUE','DAILY_COGS','DAILY_PROFIT','DAILY_ORDER_POPULATION',
 'VALID_MARGIN_DENOMINATOR'}

@dataclass(frozen=True)
class Period:
    start:str
    end_exclusive:str

def verified_report(report:dict)->None:
    if report.get('phase')!='4B.5.3' or report.get('status')!='REVIEW_ELIGIBLE' or report.get('execution_approved') is not False:
        raise FinanceGateError('Missing successful unapproved Phase 4B.5.3 evidence')
    periods=report.get('periods')
    if not isinstance(periods,list) or len(periods)<3: raise FinanceGateError('At least three reconciled periods required')
    seen=set()
    for entry in periods:
        if entry.get('status')!='RECONCILED_FOR_REVIEW' or entry.get('execution_approved') is not False:
            raise FinanceGateError('Period has not reconciled or is inconsistent')
        dates=entry.get('period')
        if not isinstance(dates,list) or len(dates)!=2:raise FinanceGateError('Invalid evidence dates')
        require_date_pair(*dates)
        if tuple(dates) in seen: raise FinanceGateError('Repeated evidence period')
        seen.add(tuple(dates))
        checks=entry.get('checks')
        if not isinstance(checks,list):raise FinanceGateError('Missing checks')
        by_name={c.get('name'):c.get('passed') for c in checks if isinstance(c,dict)}
        if any(by_name.get(c) is not True for c in FINANCE_CHECKS):raise FinanceGateError('Missing or failed required reconciliation check')
        measurements=entry.get('measurements',{})
        if measurements.get('orders_with_items') != measurements.get('financial_orders'):
            raise FinanceGateError('Item population differs from financial population')

def sql_for(metric:str,period:Period,report:dict,*,dimension=None,joins=None)->dict:
    verified_report(report)
    if dimension or joins:raise FinanceGateError('Dimensional queries and joins are NOT approved by this evidence')
    spec=METRICS.get(metric)
    if spec is None:raise FinanceGateError('Unapproved metric')
    lo,hi=require_date_pair(period.start,period.end_exclusive)
    # This initial gate intentionally limits dates to the three exact audited periods.
    if [lo.isoformat(),hi.isoformat()] not in [p['period'] for p in report['periods']]:
        raise FinanceGateError('Period has not been reconciled; do not extrapolate approval')
    source,date_col,expr,unit=spec
    if source not in FINANCE_SOURCES:raise FinanceGateError('Disallowed source')
    schema,relation=source.split('.')
    safe_date=date_expr('t0',date_col)
    sql=(f'SELECT COUNT(*) AS eligible_source_rows, {expr} AS metric_value '
         f'FROM "{schema}"."{relation}" t0 '
         f"WHERE {safe_date} >= DATE '{lo.isoformat()}' AND {safe_date} < DATE '{hi.isoformat()}' LIMIT 1")
    return {'metric':metric,'source':source,'unit':unit,'period':[lo.isoformat(),hi.isoformat()],
            'sql':sql,'allowed_dimension_ids':[],'allowed_join_ids':[],
            'execution_status':'GATED_SINGLE_SOURCE_EXACT_RECONCILED_PERIOD',
            'caution':'Modeled finance values; this is descriptive measurement, not accounting audit or causal attribution.'}

def validate_measurement(plan:dict,response:dict)->dict:
    rows=response.get('rows') if isinstance(response,dict) else None
    if isinstance(response,dict) and response.get('ok') is False:raise FinanceGateError('MCP rejected SQL')
    if not isinstance(rows,list) or len(rows)!=1 or not isinstance(rows[0],dict):
        raise FinanceGateError('Expected exactly one governed aggregate row')
    row=rows[0]
    try:
        coverage=int(row['eligible_source_rows'])
        if coverage<=0:raise FinanceGateError('No period coverage; not a zero metric')
        value=Decimal(str(row['metric_value']))
        if not value.is_finite():raise FinanceGateError('Non-finite metric')
    except (KeyError,TypeError,ValueError,InvalidOperation) as exc:raise FinanceGateError('Invalid metric or source coverage') from exc
    return {'metric':plan['metric'],'period':plan['period'],'source':plan['source'],
            'eligible_source_rows':coverage,'metric_value':str(value),'unit':plan['unit'],
            'status':'MEASURED_WITH_SCOPE_LIMITS','causal_claim':False}

def compare(a:dict,b:dict)->dict:
    if a['metric']!=b['metric'] or a['unit']!=b['unit']:raise FinanceGateError('Incompatible metric comparison')
    left,right=Decimal(a['metric_value']),Decimal(b['metric_value'])
    delta=right-left
    pct=None if left==0 else delta/abs(left)*100
    return {'metric':a['metric'],'before':a,'after':b,'absolute_change':str(delta),
            'relative_change_pct':None if pct is None else str(pct),
            'warning':('Undefined relative change: zero baseline' if pct is None else
                       'Percentage point difference, not percent change' if a['unit']=='percent' else
                       'Relative change uses absolute baseline; sign crossings require caution'),
            'causal_claim':False}
