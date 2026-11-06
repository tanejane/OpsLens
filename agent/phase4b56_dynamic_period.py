"""On-demand period reconciliation, separate from metric/dimension approval.

Existing Phase 4B.5.3 SQL/evaluator and Phase 4B.5.4 metric definitions
are the single sources of truth. This module deliberately does NOT extend
GraphPlanner/NL access and never authorizes joins or dimensions.
"""
from __future__ import annotations
from agent.investigation_result import retain_validated
from datetime import date
from hashlib import sha256
from decimal import Decimal
from agent.phase4b53_eligibility import Period as AuditPeriod, queries, assess
from agent.phase4b54_governed_finance import METRICS, FINANCE_SOURCES, FINANCE_CHECKS, FinanceGateError, validate_measurement
from agent.phase4b43_graph_planner import date_expr, require_date_pair

class DynamicPeriodRejected(FinanceGateError):
    pass


def requested_period(start: str, end_exclusive: str) -> AuditPeriod:
    lo, hi = require_date_pair(start, end_exclusive)
    if (hi-lo).days > 366:
        raise DynamicPeriodRejected('Period exceeds 366 days; split into bounded intervals')
    return AuditPeriod(lo.isoformat(), hi.isoformat())


def audit_queries(period: AuditPeriod) -> dict[str, str]:
    return queries(period)


def audit_token(period: AuditPeriod, raw_rows: dict[str, dict]) -> dict:
    """Build a process-local validation token from actual four MCP results.

    Not a cryptographic signature or persistent approval; caller must keep the
    returned token paired with the same live database invocation.
    """
    if set(raw_rows) != {'cohort','finance','daily','integrity'}:
        raise DynamicPeriodRejected('Four reconciler results required')
    verdict=assess(period, raw_rows)
    if verdict['status'] != 'RECONCILED_FOR_REVIEW':
        raise DynamicPeriodRejected('Period reconciliation failed: ' + ','.join(
            c['name'] for c in verdict.get('checks',[]) if not c['passed']) +
            ';' + ','.join(verdict.get('issues',[])))
    checks={c['name']:c['passed'] for c in verdict['checks']}
    if any(checks.get(name) is not True for name in FINANCE_CHECKS):
        raise DynamicPeriodRejected('Required reconciliation check missing/failed')
    if verdict.get('execution_approved') is not False:
        raise DynamicPeriodRejected('Unexpected audit execution approval')
    return {'kind':'ephemeral_period_reconciliation','period':[period.start,period.end],
            'checks':verdict['checks'],'measurements':verdict['measurements'],
            'status':'RECONCILED_FOR_REVIEW','execution_approved':False,
            'scope':'single_source_total_only',
            'caveat':'Nonempty coverage and matching aggregates do not prove continuous date completeness.'}


def compile_metric(metric: str, period: AuditPeriod, token: dict, *, dimensions=(), joins=()) -> dict:
    if dimensions or joins:
        raise DynamicPeriodRejected('No dimension or join approvals from period audit')
    if token.get('kind')!='ephemeral_period_reconciliation' or token.get('status')!='RECONCILED_FOR_REVIEW' or token.get('execution_approved') is not False:
        raise DynamicPeriodRejected('Successful runtime reconciliation token required')
    if token.get('period') != [period.start, period.end] or token.get('scope')!='single_source_total_only':
        raise DynamicPeriodRejected('Token scope or period mismatch')
    checks={c.get('name'):c.get('passed') for c in token.get('checks',[]) if isinstance(c,dict)}
    if any(checks.get(name) is not True for name in FINANCE_CHECKS):
        raise DynamicPeriodRejected('Incomplete runtime reconciliation evidence')
    observations=token.get('measurements',{})
    if (observations.get('financial_orders',0)<=0 or
        observations.get('orders_with_items')!=observations.get('financial_orders')):
        raise DynamicPeriodRejected('Invalid source population')
    spec=METRICS.get(metric)
    if spec is None:
        raise DynamicPeriodRejected('Unregistered finance metric')
    source,col,expression,unit=spec
    if source not in FINANCE_SOURCES:
        raise DynamicPeriodRejected('Unapproved relation')
    schema,table=source.split('.')
    dt=date_expr('t0',col)
    sql=(f'SELECT COUNT(*) AS eligible_source_rows, {expression} AS metric_value '
         f'FROM "{schema}"."{table}" t0 '
         f"WHERE {dt} >= DATE '{period.start}' AND {dt} < DATE '{period.end}' LIMIT 1")
    return {'metric':metric,'unit':unit,'source':source,'period':[period.start,period.end],
            'sql':sql,'execution_status':'EPHEMERAL_RUNTIME_RECONCILED_TOTAL_ONLY',
            'allowed_dimension_ids':[],'allowed_join_ids':[], 'causal_claim':False}


@retain_validated
def measurement_evidence(plan: dict, mcp_response: dict, token: dict) -> dict:
    if plan.get('period')!=token.get('period'):
        raise DynamicPeriodRejected('Period token mismatch')
    measure=validate_measurement(plan,mcp_response)
    return {'kind':'governed_measurement','metric_id':measure['metric'],
        'value':measure['metric_value'],'unit':measure['unit'],'source':measure['source'],
        'source_population_rows':measure['eligible_source_rows'],'period':measure['period'],
        'status':'MEASURED_WITH_SCOPE_LIMITS','causal_claim':False,
        'period_reconciliation_status':token['status'],
        'permission':'ephemeral_single_source_total',
        'limitations':['On-demand reconciliation is not a persistent metric or join approval',
          'Source coverage was nonempty, but continuous coverage was not independently certified',
          'Financial costs and incident adjustments are partly modeled',
          'No causal attribution from period comparisons']}
