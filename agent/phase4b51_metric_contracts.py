"""Versioned, non-executable semantic metric contract repair candidates.
No arbitrary SQL or execution approval is taken from this registry.
"""
from __future__ import annotations
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

class ContractError(ValueError): pass

# Comparisons here are independent of the LLM. Approved SQL is assembled from these fixed
# expressions, not generated from arbitrary model output.
CHECKS = {
 'orders': {'source':'commerce.orders','date':'order_purchase_timestamp',
            'expr':'COUNT(DISTINCT "order_id")','fields':['order_id','order_purchase_timestamp'], 'grain':'order'},
 'effective_revenue': {'source':'semantic.order_economics','date':'order_purchase_timestamp',
            'expr':'SUM("effective_revenue")','fields':['effective_revenue','order_purchase_timestamp','order_id'],'grain':'order'},
 'effective_contribution_profit': {'source':'semantic.order_economics','date':'order_purchase_timestamp',
            'expr':'SUM("effective_contribution_profit")','fields':['effective_contribution_profit','order_purchase_timestamp','order_id'],'grain':'order'},
 'effective_contribution_margin_pct': {'source':'semantic.order_economics','date':'order_purchase_timestamp',
            'expr':'100.0 * SUM("effective_contribution_profit") / NULLIF(SUM("effective_revenue"),0)',
            'fields':['effective_contribution_profit','effective_revenue','order_purchase_timestamp','order_id'],'grain':'order'},
 'effective_gross_margin_pct': {'source':'semantic.order_economics','date':'order_purchase_timestamp',
            'expr':'100.0 * (SUM("effective_revenue") - SUM("effective_cogs")) / NULLIF(SUM("effective_revenue"),0)',
            'fields':['effective_revenue','effective_cogs','order_purchase_timestamp','order_id'],'grain':'order'},
}

def proposed_catalog(original: dict) -> dict:
    """Return a separate repaired catalog proposal; do not modify source input."""
    result=json.loads(json.dumps(original))
    by_name={m['metric_name']:m for m in result['metrics']}
    if 'orders' not in by_name or 'contribution_margin' not in by_name:
        raise ContractError('Existing catalog missing orders/contribution_margin')
    orders=by_name['orders']
    orders.update(source_view='commerce.orders',time_field='order_purchase_timestamp',formula='COUNT(DISTINCT order_id)',grain='order; aggregatable by purchase period')
    margin=by_name['contribution_margin']
    margin.update(source_view='semantic.order_economics',time_field='order_purchase_timestamp',formula='SUM(effective_contribution_profit) / NULLIF(SUM(effective_revenue), 0)',grain='ratio of sums at order-level source')
    margin['known_limitations']=list(dict.fromkeys(margin.get('known_limitations',[])+['Fraction from 0 to 1; multiply by 100 only when displaying percent.']))
    result['version']='4b5.1-proposal'
    result['approval_status']='NOT_EXECUTION_APPROVED'
    return result

def query(metric: str, start: str, end: str) -> str:
    import datetime
    if metric not in CHECKS: raise ContractError('Unknown metric ID')
    try:
        s=datetime.date.fromisoformat(start); e=datetime.date.fromisoformat(end)
    except (TypeError,ValueError): raise ContractError('Invalid ISO dates') from None
    if not s < e: raise ContractError('Invalid half-open period')
    spec=CHECKS[metric]
    relation=spec['source']; schema,table=relation.split('.')
    date_col=spec['date']
    # Read-only SQL guarded for text dates; exact source names/expressions are fixed registry literals.
    safe_date=f'''(CASE WHEN pg_input_is_valid(NULLIF(BTRIM("{date_col}"::text), ''), 'timestamp without time zone') THEN NULLIF(BTRIM("{date_col}"::text), '')::timestamp ELSE NULL END)'''
    return (f'SELECT COUNT(*) AS eligible_source_rows, {spec["expr"]} AS metric_value '
            f'FROM "{schema}"."{table}" WHERE {safe_date} >= DATE \'{s.isoformat()}\' '
            f'AND {safe_date} < DATE \'{e.isoformat()}\' LIMIT 1')

def assess(metric: str, row: dict, *, audit: dict) -> dict:
    spec=CHECKS[metric]
    source=audit.get('sources',{}).get(spec['source'],{})
    issues=[]
    if source.get('checks',{}).get('grain',{}).get('status')!='VERIFIED':issues.append('SOURCE_GRAIN_UNVERIFIED')
    absent=set(spec['fields'])-set(source.get('live_columns',[]))
    if absent:issues.append('MISSING_COLUMNS:'+','.join(sorted(absent)))
    count=row.get('eligible_source_rows')
    if not isinstance(count,int) or count<0:issues.append('INVALID_COUNT')
    elif count==0:issues.append('NO_PERIOD_COVERAGE')
    value=row.get('metric_value')
    if value is None:issues.append('NULL_METRIC')
    if metric.endswith('margin_pct') and value is not None:
        try:
            if not -100000 < float(value) < 100000:issues.append('OUT_OF_BOUNDS')
        except (ValueError,TypeError): issues.append('INVALID_VALUE')
    return {'metric':metric,'source':spec['source'],'eligible_source_rows':count,'metric_value':value,
            'assessment':'REVIEW_REQUIRED' if not issues else 'BLOCKED', 'issues':issues,
            'execution_approved':False,
            'note':'Structural and value checks alone do not certify business reconciliation or dimension safety.'}
