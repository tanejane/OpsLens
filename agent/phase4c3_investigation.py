"""Phase 4C.3: conservative, governed, multi-metric investigation workflow.

No LLM SQL, no incident ground-truth access, no inferred comparison dates,
no causal assertions. Uses existing Phase 4B57 audited finance executor.
"""
from __future__ import annotations
from dataclasses import dataclass, field
from copy import deepcopy
from decimal import Decimal
from typing import Any
from agent.phase4b57_nl_dynamic_finance import execute as finance_execute
from agent.phase4b56_dynamic_period import requested_period

class InvestigationRejected(ValueError): pass

@dataclass(frozen=True)
class InvestigationRequest:
    before_start: str
    before_end: str
    after_start: str
    after_end: str
    focus: str = 'revenue_profit_divergence'

@dataclass
class InvestigationState:
    request: InvestigationRequest
    observations: dict[str, Any] = field(default_factory=dict)
    premise: dict[str, Any] = field(default_factory=dict)
    findings: list[dict[str, Any]] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    result: dict[str, Any] = field(default_factory=dict)

def _number(evidence: dict) -> Decimal:
    measurement = evidence['measurement']
    if measurement.get('status') != 'MEASURED_WITH_SCOPE_LIMITS':
        raise InvestigationRejected('Unverified metric evidence')
    value = Decimal(str(measurement['value']))
    if not value.is_finite():
        raise InvestigationRejected('Non-finite metric evidence')
    return value

def validate_request(req: InvestigationRequest) -> tuple[Any, Any]:
    if req.focus != 'revenue_profit_divergence':
        raise InvestigationRejected('This first investigation path supports revenue/profit divergence only')
    before = requested_period(req.before_start,req.before_end)
    after = requested_period(req.after_start,req.after_end)
    if before.end > after.start:
        raise InvestigationRejected('Comparison must have disjoint, chronological periods')
    return before,after

async def collect_evidence(state: InvestigationState, reader) -> InvestigationState:
    before,after=validate_request(state.request)
    # Each call passes through audited dynamic-period verification and MCP.
    for metric in ('effective_revenue','effective_contribution_profit','effective_cogs'):
        state.observations[metric] = await finance_execute(metric,before,after,reader)
        evidence=state.observations[metric]
        if evidence.get('causal_claim') is not False or 'before' not in evidence:
            raise InvestigationRejected('Comparison evidence was incomplete or asserted causality')
        for key in ('measurement','before'):
            row=evidence[key]
            if row.get('source')!='semantic.order_economics' or row.get('period_reconciliation_status')!='RECONCILED_FOR_REVIEW':
                raise InvestigationRejected('Unreconciled or wrong-source metric')
            if int(row.get('source_population_rows',0))<=0:
                raise InvestigationRejected('Missing source population')
    return state

def verify_premise(state: InvestigationState) -> InvestigationState:
    rev = state.observations['effective_revenue']
    prof = state.observations['effective_contribution_profit']
    change_rev=_number(rev)-Decimal(str(rev['before']['value']))
    change_profit=_number(prof)-Decimal(str(prof['before']['value']))
    state.premise={
        'revenue_increased':change_rev>0,
        'contribution_profit_decreased':change_profit<0,
        'revenue_delta':str(change_rev),
        'contribution_profit_delta':str(change_profit),
        'divergence_confirmed':change_rev>0 and change_profit<0,
    }
    return state

def decompose(state: InvestigationState) -> InvestigationState:
    # Accounting identity, NOT driver-specific causal attribution:
    # delta profit = delta revenue - delta COGS - delta other net charges.
    v=state.observations
    def delta(metric):
        e=v[metric]
        return _number(e)-Decimal(str(e['before']['value']))
    dr,dc,dp=(delta(k) for k in ('effective_revenue','effective_cogs','effective_contribution_profit'))
    other=dr-dc-dp
    if dr-dc-other!=dp:
        raise InvestigationRejected('Decomposition does not balance')
    state.findings=[
        {'component':'effective_revenue','delta':str(dr),'contribution_to_profit_delta':str(dr)},
        {'component':'effective_cogs','delta':str(dc),'contribution_to_profit_delta':str(-dc)},
        {'component':'other_net_charges_residual','delta':str(other),'contribution_to_profit_delta':str(-other),
         'limitation':'Residual includes all other modeled charges and adjustments; it is NOT a verified marketing/refund/fulfillment breakdown.'}
    ]
    return state

def compose(state: InvestigationState) -> InvestigationState:
    req=state.request
    confirmed=state.premise['divergence_confirmed']
    state.result={
        'route':'investigation','status':'DESCRIPTIVE_DECOMPOSITION_ONLY' if confirmed else 'PREMISE_NOT_CONFIRMED',
        'executable':True,'causal_claim':False,'focus':req.focus,
        'periods':{'before':[req.before_start,req.before_end],'after':[req.after_start,req.after_end]},
        'premise':state.premise,'findings':state.findings,
        'metric_results':deepcopy(state.observations),
        'evidence':{metric:{'before':v['before'],'after':v['measurement']} for metric,v in state.observations.items()},
        'hypotheses_not_tested':['Marketing spend changes','Refund changes','Fulfillment/payment costs','Product mix','Incident-specific adjustments'],
        'limitations':[
            'This is a descriptive accounting bridge, not causal root-cause attribution',
            'Other net charges are a residual; component-level breakdown has not been governed or verified',
            'The finance layer contains modeled costs and incident adjustments',
            'Period source non-emptiness does not independently certify continuous coverage',
            'Different periods may differ in seasonality, mix, population and exposure',
        ],
        'next_step':'Register and verify auditable cost-component metrics before testing individual drivers',
    }
    return state

async def investigate(req: InvestigationRequest, reader) -> dict:
    """Sequential fallback uses exactly the same nodes without requiring LangGraph."""
    state=InvestigationState(req)
    validate_request(req)
    await collect_evidence(state,reader)
    verify_premise(state)
    decompose(state)
    return compose(state).result

def build_langgraph(reader):
    """Optional LangGraph StateGraph with explicit, inspectable nodes."""
    from langgraph.graph import StateGraph, END
    from typing import TypedDict
    class GraphState(TypedDict):
        investigation: InvestigationState
    async def gather(s:GraphState):
        return {'investigation':await collect_evidence(s['investigation'],reader)}
    def premise(s:GraphState):
        return {'investigation':verify_premise(s['investigation'])}
    def bridge(s:GraphState):
        return {'investigation':decompose(s['investigation'])}
    def report(s:GraphState):
        return {'investigation':compose(s['investigation'])}
    graph=StateGraph(GraphState)
    graph.add_node('collect_governed_finance_evidence',gather)
    graph.add_node('verify_premise',premise)
    graph.add_node('decompose_accounting_bridge',bridge)
    graph.add_node('report_with_uncertainty',report)
    graph.set_entry_point('collect_governed_finance_evidence')
    graph.add_edge('collect_governed_finance_evidence','verify_premise')
    graph.add_edge('verify_premise','decompose_accounting_bridge')
    graph.add_edge('decompose_accounting_bridge','report_with_uncertainty')
    graph.add_edge('report_with_uncertainty',END)
    return graph.compile()
