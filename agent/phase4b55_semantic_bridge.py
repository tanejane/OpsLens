"""Additive semantic routing for finance + existing graph metrics.

No arbitrary SQL from an LLM. Finance gates require exact audited period evidence.
Graph route preserves all GraphPlanner source/grain/edge restrictions.
"""
from __future__ import annotations
from dataclasses import dataclass
from decimal import Decimal
from typing import Any
from agent.phase4b43_graph_planner import AnalysisRequest, GraphPlanner
from agent.phase4b54_governed_finance import (
    METRICS, Period, sql_for, validate_measurement, compare, FinanceGateError
)

class BridgeRejected(ValueError):
    pass

@dataclass(frozen=True)
class SemanticQuery:
    metric: str
    start: str
    end_exclusive: str
    dimensions: tuple[str, ...] = ()
    order: str = 'desc'
    limit: int = 10


def compile_query(query: SemanticQuery, *, reconciliation: dict, graph_planner: GraphPlanner | None = None) -> dict:
    """Strict dispatch by registered metric ID, never by question patterns."""
    if query.metric in METRICS:
        if query.dimensions:
            raise BridgeRejected('Finance dimensions require separate measure-safe approval')
        if query.order != 'desc' or query.limit != 10:
            raise BridgeRejected('Finance ranking/limit unsupported; use defaults')
        plan = sql_for(query.metric, Period(query.start, query.end_exclusive), reconciliation)
        return {'route': 'governed_finance', 'plan': plan, 'metric': query.metric,
                'period': list(plan['period']), 'approved_dimensions': [], 'causal_claim': False}
    if graph_planner is None:
        raise BridgeRejected('GraphPlanner required for non-finance metrics')
    req = AnalysisRequest(query.metric, query.dimensions, query.start, query.end_exclusive,
                          query.order, query.limit)
    plan = graph_planner.compile(req)
    return {'route': 'existing_graph', 'plan': plan, 'metric': query.metric,
            'period': [query.start,query.end_exclusive], 'approved_dimensions': list(query.dimensions),
            'causal_claim': False}


def finance_evidence(compiled: dict, mcp_result: dict) -> dict:
    if compiled.get('route') != 'governed_finance':
        raise BridgeRejected('Finance evidence validator cannot validate graph results')
    measurement = validate_measurement(compiled['plan'], mcp_result)
    return {'kind': 'governed_measurement', 'route': 'governed_finance',
            'metric_id': measurement['metric'], 'source': measurement['source'],
            'period': measurement['period'], 'grain': 'order',
            'source_population_rows': measurement['eligible_source_rows'],
            'value': measurement['metric_value'], 'unit': measurement['unit'],
            'definition_provenance': ('modeled effective financial economics' if
              measurement['source']=='semantic.order_economics' else 'observed commerce orders'),
            'status': measurement['status'], 'limitations': [
              'Only exact pre-reconciled periods are authorized by this gate',
              'Single-source totals only; no seller/category breakdown approved',
              'Descriptive evidence does not establish causes'],
            'causal_claim': False, 'execution_permission_scope': 'exact_period_single_source',
            'sql': compiled['plan']['sql']}


def finance_comparison(before: dict, after: dict) -> dict:
    if before.get('route')!='governed_finance' or after.get('route')!='governed_finance':
        raise BridgeRejected('Comparison requires two finance evidence records')
    if before['metric_id'] != after['metric_id'] or before['unit'] != after['unit']:
        raise BridgeRejected('Incompatible measures')
    def measurement(e):
        return {'metric':e['metric_id'],'unit':e['unit'],'metric_value':e['value'],
                'period':e['period'],'source':e['source'], 'eligible_source_rows':e['source_population_rows']}
    result = compare(measurement(before),measurement(after))
    return {'kind':'period_comparison','metric_id':before['metric_id'],
            'before':before,'after':after,'absolute_change':result['absolute_change'],
            'relative_change_pct':result['relative_change_pct'], 'warning':result['warning'],
            'causal_claim': False, 'limitations': ['Periods may not be comparable without seasonality or mix controls']}
