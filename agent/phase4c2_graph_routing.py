"""Phase 4C.2 additive graph-analytics execution route, no new SQL permissions.

Uses GeminiSemanticInterpreter -> ground -> GraphPlanner.compile -> read-only MCP.
Only graph results with rows and valid metric values update graph context.
Finance state is left untouched; cross-domain inheritance is never implicit.
"""
from __future__ import annotations
from agent.investigation_result import retain_validated
from dataclasses import dataclass, replace
import re
from typing import Any
from agent.phase4c1_router import (Conversation, GeminiRouter, validate_route,
    needs_reference_clarification, clarification_envelope, route_and_execute)
from agent.phase4b44_context_grounding import ground
from agent.phase4b43_graph_planner import GraphPlanner, AnalysisRequest

@dataclass(frozen=True)
class UnifiedContext:
    conversation: Conversation = Conversation()
    graph_request: AnalysisRequest | None = None
    last_successful_domain: str | None = None

class GraphRouteRejected(ValueError):
    pass

@retain_validated
def validate_graph_response(result: Any, plan: dict, req: AnalysisRequest) -> dict:
    """Validate MCP envelope, source coverage and rank tie caveat; no zero inference."""
    if not isinstance(result, dict) or result.get('ok') is False:
        raise GraphRouteRejected('MCP returned an error or malformed envelope')
    data = result.get('data', result)
    rows = data.get('rows') if isinstance(data, dict) else None
    if not isinstance(rows, list) or not rows:
        raise GraphRouteRejected('NO_SOURCE_COVERAGE_OR_EMPTY_COHORT: no rows; not a measured zero')
    if len(rows)>req.limit or not all(isinstance(row,dict) for row in rows):
        raise GraphRouteRejected('Invalid MCP row structure or result bound')
    if not all('metric_value' in row and row['metric_value'] is not None for row in rows):
        raise GraphRouteRejected('Undefined or null metric values; cannot assert ranking')
    if any(any(dim not in row for dim in req.dimensions) for row in rows):
        raise GraphRouteRejected('Missing grouped dimension field')
    return {
        'kind':'governed_graph_measurement', 'metric_id':req.metric,
        'dimensions':list(req.dimensions), 'period':[req.start_date,req.end_date_exclusive],
        'order':req.order,'limit':req.limit, 'source_relations':plan['sources'],
        'relationship_ids':plan['relationships'], 'rows':rows,
        'row_count':len(rows),'status':'MEASURED_WITH_LIMITATIONS',
        'calculation_safety':plan['safety'], 'causal_claim':False,
        'limitations':[
            'Observed rows do not certify complete period coverage or all cohort members',
            'A limited ranking may exclude other entities tied at the cutoff',
            'Entities with no qualifying events do not appear in event-based rankings',
            'This measurement is descriptive and not evidence of causation',
        ] if req.dimensions else [
            'Aggregate is descriptive, not causal',
            'Source period coverage must be assessed independently from nonempty results',
        ]
    }

async def execute_graph(question: str, state: UnifiedContext, interpreter, planner: GraphPlanner, call_graph):
    prior = state.graph_request if state.last_successful_domain == 'graph' else None
    meaning = interpreter.interpret(question, planner.map, prior)
    grounded = ground(meaning, planner.map, prior)
    if grounded.status!='READY' or grounded.request is None:
        return ({'route':'graph_analytics','status':grounded.status,
                 'executable':False,'reason':grounded.message,'causal_claim':False},state)
    req=grounded.request
    plan=planner.compile(req)
    response=await call_graph(plan['sql'],req,plan)
    evidence=validate_graph_response(response,plan,req)
    return ({'route':'graph_analytics','status':evidence['status'],
             'executable':True,'evidence':evidence,'causal_claim':False},
            replace(state,graph_request=req,last_successful_domain='graph'))

async def dispatch(question: str, state:UnifiedContext, router, finance_interpreter, finance_reader,
                   graph_interpreter,planner:GraphPlanner,graph_reader):
    """Unified entry point. Routing cannot override graph compiler authorization."""
    # Existing finance route keeps its tested state rescue and clarification behavior.
    if needs_reference_clarification(question):
        return clarification_envelope(question,state.conversation),state
    proposal=router.propose(question,state.conversation)
    plan=validate_route(proposal)
    # Last successful graph request is the only authorized context for a bare
    # month/year graph follow-up. The graph interpreter and grounding still
    # independently validate all inherited fields and date boundaries.
    period_only = bool(re.fullmatch(
        r'\s*(?:what\s+about|how\s+about|and|for)\s+'
        r'(?:january|february|march|april|may|june|july|august|september|october|november|december)\s+\d{4}\s*[?.!]?\s*',
        question,re.IGNORECASE))
    if (period_only and state.last_successful_domain=='graph' and state.graph_request is not None
            and plan.route in ('clarification','finance_measure')):
        return await execute_graph(question,state,graph_interpreter,planner,graph_reader)
    if plan.route=='graph_analytics':
        return await execute_graph(question,state,graph_interpreter,planner,graph_reader)
    # Use already-tested finance routing for finance turns; pass the precomputed
    # proposal to prevent a second router call and routing drift.
    class FixedRouter:
        def propose(self, _question, _context):return proposal
    output,new_conversation=await route_and_execute(question,state.conversation,
        FixedRouter(),finance_interpreter,finance_reader)
    if new_conversation!=state.conversation:
        return output,replace(state,conversation=new_conversation,last_successful_domain='finance')
    return output,state
