"""Phase 4C.8 capability registry. Descriptive metadata; NEVER grants SQL authorization.

Capabilities tagged 'available' are still gated by their existing executors.
Do not use entries in this registry as evidence that a join/metric is approved.
"""
from dataclasses import dataclass
from typing import Literal

Status = Literal['available', 'not_governed', 'not_connected']

@dataclass(frozen=True)
class Capability:
    id: str
    domains: tuple[str, ...]
    intents: tuple[str, ...]
    status: Status
    executor: str | None
    prerequisites: tuple[str, ...]
    evidence: str
    limitations: tuple[str, ...] = ()

REGISTRY: tuple[Capability, ...] = (
    Capability('finance_premise', ('finance',), ('financial_divergence',), 'available',
               'phase4c3_investigation', ('explicit_before_and_after_periods','audited_finance_totals'),
               'effective_revenue/effective_contribution_profit/effective_cogs',
               ('Modelled costs', 'Descriptive; cannot establish causation')),
    Capability('finance_cost_components', ('finance',), ('financial_divergence',), 'available',
               'phase4c4_drivers', ('finance_premise','approved_cost_view','population_reconciliation'),
               'refund/marketing/fulfilment/incentive/processing totals', ('Modelled financial charges',)),
    Capability('finance_per_order_intensity', ('finance',), ('financial_divergence',), 'available',
               'phase4c7_adaptive', ('finance_cost_components','reconciled_order_population'),
               'per-eligible-order costs', ('Different cohorts; no causal inference',)),
    Capability('graph_seller_ranking', ('commerce',), ('ranking',), 'available',
               'phase4c2_graph_routing', ('approved_graph_metric','audited_join_path','explicit_period'),
               'distinct order count by seller', ('Only approved graph paths execute',)),
    Capability('delivery_diagnostics', ('operations',), ('delivery_issue',), 'not_connected', None,
               ('verified_delivery_metrics','period_coverage','join_contract'), 'not yet available'),
    Capability('review_diagnostics', ('customer_experience',), ('satisfaction_issue',), 'not_connected', None,
               ('review_grain_audit','verified_review_metrics','cohort_contract'), 'not yet available'),
    Capability('campaign_incrementality', ('marketing',), ('marketing_effectiveness',), 'not_governed', None,
               ('campaign_exposure_definition','counterfactual_design','outcome_linkage'), 'not yet available'),
    Capability('category_profitability', ('product',), ('product_mix_profit',), 'not_governed', None,
               ('item_level_cost_allocation','fanout_audit','metric_reconciliation'), 'not yet available'),
)


def registry_snapshot() -> list[dict]:
    return [{'id':c.id,'domains':list(c.domains),'intents':list(c.intents),
             'status':c.status,'executor':c.executor,'prerequisites':list(c.prerequisites),
             'evidence':c.evidence,'limitations':list(c.limitations)} for c in REGISTRY]


def find_capability(cap_id: str) -> Capability | None:
    return next((c for c in REGISTRY if c.id == cap_id), None)
