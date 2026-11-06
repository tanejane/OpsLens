from __future__ import annotations
from typing import Literal
from pydantic import BaseModel, Field, model_validator

ActionType = Literal['metric_definition','schema_discovery','structured_test','knowledge_search','stop']
HypothesisId = Literal['H1','H2','H3','H4']

class PlannerDecision(BaseModel):
    action_type: ActionType
    hypothesis_id: HypothesisId | None = None
    evidence_needed: str = Field(min_length=1, max_length=500)
    rationale: str = Field(min_length=1, max_length=800)
    query_hint: str | None = Field(default=None, max_length=500)
    confidence: float = Field(ge=0.0, le=1.0)

    @model_validator(mode='after')
    def check_semantics(self):
        if self.action_type in {'structured_test','knowledge_search'} and self.hypothesis_id is None:
            raise ValueError('Hypothesis-specific actions require hypothesis_id.')
        if self.action_type == 'stop':
            self.hypothesis_id = None
        if self.query_hint:
            low = self.query_hint.lower()
            if any(t in low for t in ['select ','insert ','update ','delete ','drop ','alter ','truncate ',';']):
                raise ValueError('Planner query_hint must not contain executable SQL.')
        return self
