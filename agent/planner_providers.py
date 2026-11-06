from __future__ import annotations
import json, os
from abc import ABC, abstractmethod
from typing import Any
from dotenv import load_dotenv
from agent.planner_contract import PlannerDecision
load_dotenv()

class PlannerProvider(ABC):
    @abstractmethod
    def plan(self, snapshot: dict[str, Any]) -> PlannerDecision: ...

class FakePlannerProvider(PlannerProvider):
    def plan(self, s: dict[str, Any]) -> PlannerDecision:
        ev=set(s['evidence_ids']); st=s['hypothesis_statuses']
        def d(a,h,e,r,q=None,c=.9):
            return PlannerDecision(action_type=a,hypothesis_id=h,evidence_needed=e,rationale=r,query_hint=q,confidence=c)
        if 'E-METRIC-DEFINITION' not in ev:
            return d('metric_definition',None,'Governed definition of contribution profit.','Understand the metric before causal analysis.',c=.99)
        if 'E-OUTCOME' not in ev:
            return d('structured_test','H1','Confirm revenue-up/profit-down pattern.','Outcome confirmation must precede causal attribution.','confirm flagship outcome',.98)
        if st['H1']=='UNTESTED':
            return d('structured_test','H1','Compare COGS growth with revenue growth.','Test supplier/COGS pressure.','supplier costs versus revenue',.92)
        if st['H1']=='SUPPORTED' and 'E-H1-DOC' not in ev:
            return d('knowledge_search','H1','Find supplier-cost corroboration.','Corroborate measured evidence.','supplier costs increased during March profitability decline',.91)
        if st['H2']=='UNTESTED' and 'E-H2-SCHEMA' not in ev:
            return d('schema_discovery','H2','Inspect finance.daily_pnl schema.','Do not guess governed fields.','finance daily pnl marketing fields',.96)
        if st['H2']=='UNTESTED':
            return d('structured_test','H2','Measure marketing economics.','Marketing may explain revenue growth with profit decline.','marketing cost across incident window',.94)
        if st['H2']=='SUPPORTED' and 'E-H2-DOC' not in ev:
            return d('knowledge_search','H2','Find GrowthMax corroboration.','Corroborate structured marketing evidence.','GrowthMax campaign spend incentives',.93)
        if st['H3']=='UNTESTED':
            return d('structured_test','H3','Check product-mix overlap.','Test competing explanation.','product mix incident overlap',.85)
        if st['H4']=='UNTESTED' and 'E-H4-SCHEMA' not in ev:
            return d('schema_discovery','H4','Inspect finance.daily_pnl refund fields.','Do not guess governed fields.','finance daily pnl refund fields',.90)
        if st['H4']=='UNTESTED':
            return d('structured_test','H4','Measure refund movement.','Returns/CX may be secondary.','refund movement across incident window',.86)
        return d('stop',None,'No additional core evidence required.','All core hypotheses are evidence-resolved.',c=.98)

class OpenAIResponsesPlannerProvider(PlannerProvider):
    def __init__(self, model: str | None=None):
        from openai import OpenAI
        self.client=OpenAI()
        self.model=model or os.getenv('OPSLENS_PLANNER_MODEL') or 'gpt-6-luna'
    def plan(self, snapshot: dict[str, Any]) -> PlannerDecision:
        schema=PlannerDecision.model_json_schema()
        instructions=('You plan one next action for a governed business investigation. Never write SQL, invent columns, claim unseen evidence, or stop while core hypotheses are untested. Prefer schema discovery before structured tests when schema is unknown. Documents corroborate; they do not automatically prove causality. Return only the required structured object.')
        r=self.client.responses.create(model=self.model,instructions=instructions,input=[{'role':'user','content':'Current investigation state:\n'+json.dumps(snapshot,ensure_ascii=False,indent=2)}],text={'format':{'type':'json_schema','name':'opslens_planner_decision','schema':schema,'strict':True}})
        return PlannerDecision.model_validate_json(r.output_text)

def make_planner_provider(name: str | None=None) -> PlannerProvider:
    p=(name or os.getenv('OPSLENS_PLANNER_PROVIDER') or 'fake').lower()
    if p=='fake': return FakePlannerProvider()
    if p=='openai': return OpenAIResponsesPlannerProvider()
    raise ValueError(f'Unsupported planner provider: {p}')
