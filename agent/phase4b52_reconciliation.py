"""Phase 4B.5.2: read-only, multi-period semantic metric reconciliation.

Never mutates runtime contracts and never approves a join/metric for execution.
"""
from __future__ import annotations
from dataclasses import dataclass
from datetime import date
from decimal import Decimal, InvalidOperation
from typing import Any

class ReconciliationError(ValueError):
    pass

@dataclass(frozen=True)
class Period:
    start: str
    end: str
    def __post_init__(self):
        try:
            a, b = date.fromisoformat(self.start), date.fromisoformat(self.end)
        except (ValueError, TypeError):
            raise ReconciliationError('INVALID_PERIOD') from None
        if a >= b:
            raise ReconciliationError('INVALID_PERIOD')

# SQL identifiers and expressions are fixed in code, never supplied by model output.
# Date cast supports the existing text-based Olist timestamp and date fields.
def date_expr(alias: str, field: str) -> str:
    allowed = {('o','order_purchase_timestamp'),('e','order_purchase_timestamp'),('d','business_date')}
    if (alias, field) not in allowed:
        raise ReconciliationError('UNAPPROVED_DATE_FIELD')
    c=f'{alias}."{field}"'
    x=f"NULLIF(BTRIM({c}::text), '')"
    return f"(CASE WHEN pg_input_is_valid({x}, 'timestamp without time zone') THEN {x}::timestamp ELSE NULL END)"

def window(expr: str, p: Period) -> str:
    return f"{expr} >= DATE '{p.start}' AND {expr} < DATE '{p.end}'"

def queries(p: Period) -> dict[str,str]:
    ow=window(date_expr('o','order_purchase_timestamp'), p)
    ew=window(date_expr('e','order_purchase_timestamp'), p)
    dw=window(date_expr('d','business_date'), p)
    # Not joining order_items: preserves order-level measures and avoids item fanout.
    return {
      'population': ("SELECT COUNT(*) AS placed_orders, COUNT(e.order_id) AS represented_orders, "
       "COUNT(*) FILTER (WHERE e.order_id IS NULL) AS unrepresented_orders, "
       "COUNT(*) FILTER (WHERE e.order_id IS NULL AND o.order_status='canceled') AS missing_canceled, "
       "COUNT(*) FILTER (WHERE e.order_id IS NULL AND o.order_status='unavailable') AS missing_unavailable, "
       "COUNT(*) FILTER (WHERE e.order_id IS NULL AND o.order_status NOT IN ('canceled','unavailable')) AS missing_other, "
       "COUNT(*) FILTER (WHERE e.order_id IS NULL AND o.order_status IS NULL) AS missing_status_null "
       'FROM "commerce"."orders" o LEFT JOIN "semantic"."order_economics" e ON o."order_id"=e."order_id" WHERE '+ow+' LIMIT 1'),
      'economics': ("SELECT COUNT(*) AS financial_rows, COUNT(DISTINCT e.order_id) AS financial_unique_orders, "
        'SUM(e."effective_revenue") AS revenue, SUM(e."effective_cogs") AS cogs, '
        'SUM(e."effective_contribution_profit") AS contribution_profit FROM "semantic"."order_economics" e WHERE '+ew+' LIMIT 1'),
      'daily': ('SELECT COUNT(*) AS daily_rows, SUM(d."revenue") AS revenue, SUM(d."cogs") AS cogs, '
        'SUM(d."contribution_profit") AS contribution_profit, SUM(d."orders") AS orders '
        'FROM "semantic"."daily_commerce" d WHERE '+dw+' LIMIT 1'),
    }

def n(v: Any, key: str) -> Decimal:
    if v is None or isinstance(v, bool):
        raise ReconciliationError('MISSING_NUMERIC:'+key)
    try:
        d=Decimal(str(v))
    except (InvalidOperation, TypeError, ValueError):
        raise ReconciliationError('INVALID_NUMERIC:'+key) from None
    if not d.is_finite():
        raise ReconciliationError('NONFINITE_NUMERIC:'+key)
    return d

def result_for(p: Period, results: dict[str,dict], *, absolute_tolerance: Decimal=Decimal('0.05')) -> dict:
    checks=[]
    def check(code: str, ok: bool, detail: str):
        checks.append({'check':code,'passed':bool(ok),'detail':detail})
    try:
        a,b,c=(results[k] for k in ['population','economics','daily'])
        for k in ('population','economics','daily'):
            if not isinstance(results[k],dict):raise ReconciliationError('INVALID_RESULT:'+k)
        placed=n(a.get('placed_orders'),'placed_orders')
        rep=n(a.get('represented_orders'),'represented_orders')
        missing=n(a.get('unrepresented_orders'),'unrepresented_orders')
        canceled=n(a.get('missing_canceled'),'missing_canceled')
        unavailable=n(a.get('missing_unavailable'),'missing_unavailable')
        other=n(a.get('missing_other'),'missing_other')
        null=n(a.get('missing_status_null'),'missing_status_null')
        frows=n(b.get('financial_rows'),'financial_rows')
        funique=n(b.get('financial_unique_orders'),'financial_unique_orders')
        drows=n(c.get('daily_rows'),'daily_rows')
        check('POPULATION_BALANCE', placed==rep+missing, 'placed orders = represented + missing')
        check('MISSING_STATUS_BALANCE', missing==canceled+unavailable+other+null,'all missing orders accounted for by status')
        check('FINANCIAL_POPULATION_MATCH',rep==frows==funique, 'requires no financial-only orders, duplicates, or date reassignment')
        check('NO_UNEXPECTED_EXCLUSIONS',other==0 and null==0,'all missing orders canceled/unavailable; validates this period, not global eligibility policy')
        check('PERIOD_COVERAGE',placed>0 and frows>0 and drows>0,'all three sources represented in requested period')
        for field in ('revenue','cogs','contribution_profit'):
            x,y=n(b.get(field), 'financial_'+field),n(c.get(field),'daily_'+field)
            check('DAILY_RECONCILES_'+field.upper(),abs(x-y)<=absolute_tolerance, f'absolute difference {abs(x-y)} <= {absolute_tolerance}')
        # Margin algebra, independent of any LLM-proposed formula.
        rev=n(b.get('revenue'),'revenue')
        cog=n(b.get('cogs'),'cogs')
        prof=n(b.get('contribution_profit'),'contribution_profit')
        gross_margin=None if rev==0 else float(Decimal(100)*(rev-cog)/rev)
        contrib_margin=None if rev==0 else float(Decimal(100)*prof/rev)
        check('NONZERO_REVENUE_FOR_RATIOS',rev!=0,'ratios undefined when summed revenue is zero')
        # Daily orders is *not* assumed to equal orders placed: verify, and disclose mismatch without treating the metric as inherently bad.
        dorders=n(c.get('orders'),'daily_orders')
        check('DAILY_ORDERS_MATCH_FINANCIAL',dorders==funique,'daily orders compared to financially represented orders (definition must be confirmed)')
        ready=all(x['passed'] for x in checks)
        return {'period':{'start':p.start,'end_exclusive':p.end},'status':'RECONCILED_FOR_REVIEW' if ready else 'DISCREPANCIES_FOUND',
          'checks':checks,'measurements':{'placed_orders':int(placed),'financial_orders':int(funique),'missing_canceled':int(canceled),'missing_unavailable':int(unavailable),
          'effective_revenue':float(rev),'effective_cogs':float(cog),'effective_contribution_profit':float(prof),
          'effective_gross_margin_pct':gross_margin,'effective_contribution_margin_pct':contrib_margin},
          'execution_approved':False}
    except (ReconciliationError, KeyError) as exc:
        return {'period':{'start':p.start,'end_exclusive':p.end},'status':'INCONCLUSIVE', 'issues':[str(exc)],'checks':checks,'execution_approved':False}

def summary(rows: list[dict])->dict:
    return {'phase':'4b5.2','status':'REVIEW_ELIGIBLE' if rows and all(r['status']=='RECONCILED_FOR_REVIEW' for r in rows) else 'REVIEW_BLOCKED',
            'periods':rows,'execution_approved':False,
            'disclaimer':'Read-only diagnostic, not independent accounting audit; no metric, relationship, or dimensional execution is approved.'}
