"""Schema and application-side validation of new, question-specific investigation plans."""
from __future__ import annotations
import re
from typing import Literal
from pydantic import BaseModel, Field, model_validator
from agent.phase4a_context import ContextPacket

class EvidenceNeed(BaseModel):
    purpose: str = Field(min_length=12, max_length=240)
    source_kind: Literal['metric_definition','schema_discovery','structured_data','knowledge_search']
    target_relation: str | None = None
    validation_question: str = Field(min_length=12, max_length=280)

class ProposedHypothesis(BaseModel):
    hypothesis_id: str = Field(pattern=r'^H[1-9][0-9]?$')
    statement: str = Field(min_length=15, max_length=300)
    falsification_test: str = Field(min_length=15, max_length=300)
    evidence_needs: list[EvidenceNeed] = Field(min_length=1, max_length=4)
    status: Literal['UNTESTED'] = 'UNTESTED'

class InvestigationPlan(BaseModel):
    question: str = Field(min_length=5, max_length=1000)
    investigation_type: Literal['profitability','delivery','returns_cx','inventory','marketing','funnel','other']
    business_environment: Literal['olist','ga4','unknown']
    metrics: list[str] = Field(min_length=1, max_length=6)
    date_expression: str | None = Field(default=None, max_length=120)
    date_ambiguity: bool
    assumptions: list[str] = Field(default_factory=list, max_length=6)
    hypotheses: list[ProposedHypothesis] = Field(min_length=2, max_length=5)
    initial_evidence_need: str = Field(min_length=10, max_length=240)
    @model_validator(mode='after')
    def verify_ids(self):
        ids = [h.hypothesis_id for h in self.hypotheses]
        if len(set(ids)) != len(ids):
            raise ValueError('Hypothesis IDs must be unique')
        return self

class PlanRejected(ValueError):
    pass

def validate_plan(plan: InvestigationPlan, context: ContextPacket) -> InvestigationPlan:
    if plan.question.strip().casefold() != context.question.strip().casefold():
        raise PlanRejected('Plan question must match user question exactly')
    known_metrics = {str(m.get('name','')) for m in context.metric_catalog}
    unknown_metrics = set(plan.metrics) - known_metrics
    if unknown_metrics:
        raise PlanRejected(f'Unknown governed metrics: {sorted(unknown_metrics)}')
    known_relations = {str(r.get('name','')) for r in context.relation_catalog}
    for hypothesis in plan.hypotheses:
        for need in hypothesis.evidence_needs:
            if need.target_relation is not None and need.target_relation not in known_relations:
                raise PlanRejected(f'Unknown governed relation: {need.target_relation}')
            if re.search(r'\b(select|insert|update|drop|delete|alter|truncate)\s+', need.validation_question, re.I):
                raise PlanRejected('Evidence request must not contain SQL')
    if plan.business_environment == 'ga4' and any(
        n.target_relation and not n.target_relation.startswith(('behavior.', 'semantic.ga4_'))
        for h in plan.hypotheses for n in h.evidence_needs
    ):
        raise PlanRejected('GA4 and Olist must not be silently joined')
    return plan
