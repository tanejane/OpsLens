"""Deterministic, fail-closed bounded planning based on registered semantics.

Does not parse arbitrary language or execute SQL. A trusted, validated upstream
intent selects one intent identifier; the registry only supplies tool options.
"""
from dataclasses import dataclass
from agent.phase4c8_capabilities import REGISTRY, find_capability

SUPPORTED_INTENTS = frozenset({'financial_divergence','ranking','delivery_issue',
                               'satisfaction_issue','marketing_effectiveness','product_mix_profit'})
_ALLOWED_PLAN = {
    'financial_divergence': ('finance_premise','finance_cost_components','finance_per_order_intensity'),
    'ranking': ('graph_seller_ranking',),
    'delivery_issue': ('delivery_diagnostics',),
    'satisfaction_issue': ('review_diagnostics',),
    'marketing_effectiveness': ('campaign_incrementality',),
    'product_mix_profit': ('category_profitability',),
}

class PlanningRejected(ValueError):
    pass


@dataclass(frozen=True)
class PlanningRequest:
    intent: str
    explicit_periods: bool = False
    max_steps: int = 3


def plan(request: PlanningRequest) -> dict:
    if request.intent not in SUPPORTED_INTENTS:
        return {'status':'UNSUPPORTED_INTENT','intent':str(request.intent)[:100],
                'executable':False,'steps':[],'missing':[], 'causal_claim':False}
    if type(request.max_steps) is not int or not 1 <= request.max_steps <= 3:
        raise PlanningRejected('Invalid tool-step budget')
    if type(request.explicit_periods) is not bool:
        raise PlanningRejected('Invalid period grounding')
    requested = _ALLOWED_PLAN[request.intent]
    available, missing = [], []
    for key in requested:
        cap = find_capability(key)
        if cap is None:
            raise PlanningRejected('Registry reference missing')
        if cap.status != 'available' or not cap.executor:
            missing.append({'capability':cap.id, 'status':cap.status,
                            'required_validation':list(cap.prerequisites)})
        else:
            available.append({'capability':cap.id, 'executor':cap.executor,
                              'evidence':cap.evidence, 'limitations':list(cap.limitations)})
    if request.intent == 'financial_divergence' and not request.explicit_periods:
        return {'status':'NEEDS_CLARIFICATION','intent':request.intent,'executable':False,
                'steps':[], 'missing':[], 'reason':'Two explicit validated comparison periods required',
                'causal_claim':False}
    if request.intent == 'ranking':
        return {'status':'DELEGATE_TO_GOVERNED_GRAPH_PLANNER','intent':request.intent,
                'executable':False,'steps':[], 'missing':[],
                'reason':'Graph interpreter and compiler must validate metric/dimension/period',
                'causal_claim':False}
    if missing:
        return {'status':'INSUFFICIENT_GOVERNED_CAPABILITIES','intent':request.intent,
                'executable':False,'steps':[],'missing':missing,'causal_claim':False}
    steps = available[:request.max_steps]
    return {'status':'READY_FOR_EXISTING_EXECUTOR','intent':request.intent,'executable':True,
            'steps':steps,'missing':[], 'max_steps':request.max_steps,
            'reason':'Execution is still independently gated by existing audited modules',
            'causal_claim':False}


def audit_registry() -> dict:
    if len({c.id for c in REGISTRY}) != len(REGISTRY):
        raise PlanningRejected('Duplicate capability identifiers')
    if any(c.status == 'available' and not c.executor for c in REGISTRY):
        raise PlanningRejected('Executable capability missing executor')
    if any(c.status != 'available' and c.executor is not None for c in REGISTRY):
        raise PlanningRejected('Ungoverned capability declares an executor')
    for values in _ALLOWED_PLAN.values():
        if any(find_capability(v) is None for v in values):
            raise PlanningRejected('Plan references unknown capability')
    return {'status':'REGISTRY_VALID','registered':len(REGISTRY),
            'available':sum(c.status=='available' for c in REGISTRY),
            'not_connected_or_governed':sum(c.status!='available' for c in REGISTRY)}
