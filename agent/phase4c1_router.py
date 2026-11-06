"""Phase 4C.1: audited, capability-scoped request routing. No LLM-authored SQL.

This module is intentionally additive. Financial execution delegates to the proven
Phase 4B.5.7 finance interpreter, resolver and audited MCP executor.
Non-finance analytics and investigations are *planned*, never silently executed.
"""
from __future__ import annotations

from dataclasses import dataclass, field, replace
import re
from typing import Callable, Literal, Any

from agent.phase4b57_nl_dynamic_finance import Context, Interpreter, resolve, execute, mcp_query

Route = Literal['finance_measure','finance_compare','graph_analytics','investigation','knowledge','clarification','unsupported']
Capability = Literal['metric_lookup','period_comparison','ranking','time_trend','diagnostic_investigation','knowledge_retrieval','simulation']

class RoutingRejected(ValueError):
    pass

CAPABILITIES = {
    'metric_lookup': 'finance_measure',
    'period_comparison': 'finance_compare',
    'ranking': 'graph_analytics',
    'time_trend': 'graph_analytics',
    'diagnostic_investigation': 'investigation',
    'knowledge_retrieval': 'knowledge',
    'simulation': 'unsupported',
}

@dataclass(frozen=True)
class RoutingProposal:
    primary_intent: str
    required_capabilities: tuple[str, ...]
    confidence: float | None = None
    ambiguity: str | None = None

@dataclass(frozen=True)
class RoutingPlan:
    route: Route
    capabilities: tuple[str, ...]
    executable: bool
    status: str
    reason: str
    requires_investigation: bool = False

@dataclass(frozen=True)
class Conversation:
    finance: Context | None = None
    last_successful_route: str | None = None
    # No untrusted raw question or unvalidated LLM fields stored as execution context.


def validate_route(proposal: RoutingProposal) -> RoutingPlan:
    if not isinstance(proposal.primary_intent, str) or not proposal.primary_intent:
        raise RoutingRejected('Missing primary intent')
    if proposal.confidence is not None and not (0 <= proposal.confidence <= 1):
        raise RoutingRejected('Invalid confidence')
    capabilities = tuple(dict.fromkeys(proposal.required_capabilities))
    if not capabilities:
        return RoutingPlan('clarification', (), False, 'NEEDS_CLARIFICATION', 'No analytical capability specified')
    unknown = set(capabilities) - CAPABILITIES.keys()
    if unknown:
        return RoutingPlan('unsupported',capabilities,False,'UNSUPPORTED_CAPABILITY','Unregistered capabilities: '+', '.join(sorted(unknown)))
    if proposal.ambiguity:
        return RoutingPlan('clarification',capabilities,False,'NEEDS_CLARIFICATION',proposal.ambiguity[:300])
    if 'simulation' in capabilities:
        return RoutingPlan('unsupported',capabilities,False,'NOT_IMPLEMENTED','No validated scenario/simulation model available')
    if 'diagnostic_investigation' in capabilities:
        return RoutingPlan('investigation',capabilities,False,'INVESTIGATION_NOT_YET_CONNECTED','Needs premise checks, governed multi-metric hypotheses and evidence ledger',True)
    if 'ranking' in capabilities or 'time_trend' in capabilities:
        return RoutingPlan('graph_analytics',capabilities,False,'HANDOFF_REQUIRED','Existing GraphPlanner must independently validate metric, dimension, grain and coverage')
    if 'knowledge_retrieval' in capabilities:
        if len(capabilities)>1:
            return RoutingPlan('clarification',capabilities,False,'MULTI_STAGE_REQUIRED','Combined knowledge and measurement requires staged orchestration')
        return RoutingPlan('knowledge',capabilities,False,'HANDOFF_REQUIRED','Knowledge tool must apply source trust and document retrieval permissions')
    if set(capabilities) == {'metric_lookup'}:
        return RoutingPlan('finance_measure',capabilities,True,'READY_FOR_GROUNDING','Must still pass registered finance metric and dynamic-period gates')
    if set(capabilities) in ({'period_comparison'}, {'period_comparison','metric_lookup'}):
        return RoutingPlan('finance_compare',capabilities,True,'READY_FOR_GROUNDING','Must still pass registered finance metric and period checks')
    return RoutingPlan('clarification',capabilities,False,'NEEDS_CLARIFICATION','Unsupported capability combination')

ROUTER_SCHEMA = {
 'type':'OBJECT','properties':{
  'primary_intent':{'type':'STRING'},
  'required_capabilities':{'type':'ARRAY','items':{'type':'STRING','enum':list(CAPABILITIES)}},
  'confidence':{'type':'NUMBER','nullable':True},
  'ambiguity':{'type':'STRING','nullable':True},
 },'required':['primary_intent','required_capabilities']
}

class GeminiRouter:
    """LLM proposes capabilities only. Never emits executable SQL or permissions."""
    def __init__(self, model=None):
        import os
        from google import genai
        from agent.provider_policy import http_options
        key=os.getenv('GEMINI_API_KEY') or os.getenv('GOOGLE_API_KEY')
        if not key: raise RoutingRejected('GEMINI_API_KEY is not set')
        self.client=genai.Client(api_key=key,http_options=http_options())
        self.model=model or os.getenv('OPSLENS_GEMINI_MODEL','gemini-3.5-flash-lite')
    def propose(self,question: str,context: Conversation) -> RoutingProposal:
        import json
        from google.genai import types
        prompt=('Classify analytical task capabilities only. metric_lookup for a single KPI, '
                'period_comparison for comparison, ranking for top/bottom, time_trend for trends, '
                'diagnostic_investigation for why/root-cause/explain change (even when also comparing), '
                'knowledge_retrieval for methodology/data definitions, simulation for counterfactual forecasts. '
                'Multi-intent questions return ALL required capabilities. Do not write SQL, source tables, '
                'metrics, dates, permission claims or answers. If ambiguous, state ambiguity. '
                'Prefer diagnostic_investigation for explanations of business movement. '
                'If a prior successful finance metric exists, a simple follow-up such as '
                '"What about March 2018?" is metric_lookup using the prior metric; do not flag '
                'it as ambiguous solely because its metric name is omitted.')
        response=self.client.models.generate_content(
          model=self.model,contents=json.dumps({'question':question,'prior_finance_context':vars(context.finance) if context.finance else None}),
          config=types.GenerateContentConfig(system_instruction=prompt,response_mime_type='application/json',
            response_schema=ROUTER_SCHEMA,temperature=0,automatic_function_calling=types.AutomaticFunctionCallingConfig(disable=True)))
        from investigation_traces import record_model
        record_model(response,self.model,'routing')
        obj=response.parsed if response.parsed is not None else json.loads(response.text)
        if hasattr(obj,'model_dump'): obj=obj.model_dump()
        if not isinstance(obj,dict) or set(obj)-{'primary_intent','required_capabilities','confidence','ambiguity'}:
            raise RoutingRejected('Invalid router fields')
        caps=obj.get('required_capabilities',[])
        if not isinstance(caps,list) or not all(isinstance(v,str) for v in caps):
            raise RoutingRejected('Invalid capability list')
        return RoutingProposal(str(obj.get('primary_intent','')),tuple(caps),obj.get('confidence'),obj.get('ambiguity'))

# Deterministic rescue for the exact class of follow-up proven in live tests.
# This only selects the finance grounding route; it grants no SQL capability.
_PERIOD_ONLY = re.compile(
    r"^\s*(?:what\s+about|how\s+about|and|for)\s+"
    r"(?:(?:the\s+)?(?:month\s+of)\s+)?"
    r"(january|february|march|april|may|june|july|august|september|october|november|december)"
    r"\s+(\d{4})\s*[?.!]?\s*$", re.IGNORECASE
)

def is_unambiguous_finance_period_followup(question: str, conversation: Conversation) -> bool:
    """Only a bare calendar-month follow-up with validated prior finance state."""
    prior = conversation.finance
    return bool(
        prior is not None
        and conversation.last_successful_route in ('finance_measure', 'finance_compare')
        and isinstance(prior.metric_id, str) and prior.metric_id
        and _PERIOD_ONLY.fullmatch(question)
    )

# Only fully deictic, operation-free follow-ups are handled deterministically.
# A prompt like "What about March 2018?" is deliberately NOT in this set.
_VAGUE_FOLLOWUP = re.compile(
    r"^\s*(?:what|how)\s+about\s+(?:that|this|it|those|these)\s*[?.!]?\s*$"
    r"|^\s*(?:and|what about)\s+(?:then|that one)\s*[?.!]?\s*$",
    re.IGNORECASE,
)

def needs_reference_clarification(question: str) -> bool:
    return bool(_VAGUE_FOLLOWUP.fullmatch(question))

def clarification_envelope(question: str, conversation: Conversation) -> dict:
    prior = conversation.finance
    if prior and conversation.last_successful_route in ('finance_measure','finance_compare'):
        detail = (f"Could you clarify what you would like to know about {prior.metric_id} "
                  f"for {prior.start_date} to {prior.end_date_exclusive}? "
                  "For example, specify a different period, a comparison, or an investigation.")
    else:
        detail = "Could you specify a metric, period, comparison, or question to investigate?"
    return {'route':'clarification','capabilities':[], 'status':'NEEDS_CLARIFICATION',
            'executable':False,'reason':detail,'causal_claim':False}

async def route_and_execute(question: str, conversation: Conversation, router, finance_interpreter, reader) -> tuple[dict,Conversation]:
    """Atomic context commit. Failed/unsupported turns never mutate prior context."""
    # Do not ask Gemini or the finance interpreter to fill in an entirely missing
    # analytical operation. This prevents ambiguous reference questions from
    # being misrouted as executable lookups. No DB calls or state writes occur.
    if needs_reference_clarification(question):
        return clarification_envelope(question, conversation),conversation
    proposal=router.propose(question,conversation)
    plan=validate_route(proposal)
    # If the model calls an unambiguous *period-only* finance follow-up vague,
    # pass it to the existing strict finance interpreter for independent grounding.
    # The interpreter must still confirm metric, dates, and intent before any SQL.
    if (plan.route == 'clarification'
            and set(plan.capabilities) == {'metric_lookup'}
            and is_unambiguous_finance_period_followup(question, conversation)):
        plan = RoutingPlan('finance_measure', ('metric_lookup',), True,
                           'READY_FOR_GROUNDING', 'Resolved calendar-month follow-up from last successful finance context')
    envelope={'route':plan.route,'capabilities':list(plan.capabilities),'status':plan.status,
              'executable':plan.executable,'reason':plan.reason,'causal_claim':False}
    if not plan.executable:
        return envelope,conversation
    from agent.phase4b57_nl_dynamic_finance import interpret_with_retries
    intent=interpret_with_retries(finance_interpreter,question,conversation.finance)
    if intent.intent == 'clarify' and plan.route in ('finance_measure','finance_compare'):
        # The interpreter may legitimately find missing details that the router
        # did not notice. Preserve a user-facing clarification only when the
        # question has no independent analytical instructions. Everything else
        # remains a real routing disagreement and is never executed.
        if needs_reference_clarification(question):
            return clarification_envelope(question, conversation),conversation
    if plan.route=='finance_measure' and intent.intent!='measure':
        return {**envelope,'status':'ROUTING_DISAGREEMENT','executable':False,'reason':'Finance interpreter disagreed with router; no SQL executed'},conversation
    if plan.route=='finance_compare' and intent.intent!='compare':
        return {**envelope,'status':'ROUTING_DISAGREEMENT','executable':False,'reason':'Finance interpreter disagreed with router; no SQL executed'},conversation
    metric,before,after=resolve(intent,conversation.finance)
    result=await execute(metric,before,after,reader)
    new_context=replace(conversation,finance=Context(metric,after.start,after.end),last_successful_route=plan.route)
    return {**envelope,'status':'MEASURED_WITH_SCOPE_LIMITS','evidence':result},new_context
