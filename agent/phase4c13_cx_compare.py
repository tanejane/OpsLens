"""Governed two-period customer-satisfaction comparisons; no new SQL privileges.

The only SQL originates in the audited Phase 4C.11 single-period compiler.
"""
from __future__ import annotations
from datetime import date
from decimal import Decimal
import re
from agent.phase4c12_cx_nlp import CXSession, CXContext, CX_TERMS, MONTHS, month_period, resolve_metric
from agent.phase4c11_satisfaction import METRICS, measure

M = '|'.join(MONTHS)
FULL = re.compile(r'\b('+M+r')\s+(20\d{2})\b',re.I)
SHARED_YEAR = re.compile(r'\b('+M+r')\s+(?:to|and|vs\.?|versus|through)\s+('+M+r')\s+(20\d{2})\b',re.I)
COMPARE = re.compile(r'\b(compare|comparison|versus|vs\.?|between|from\b.+\bto|did\b.+\b(?:drop|fall|rise|increase|decrease|improve|worsen)|changed?\b|difference|trend)\b',re.I)
class CXComparisonRejected(ValueError):pass

def comparison_candidate(question,prev):
    return bool(COMPARE.search(question) and (CX_TERMS.search(question) or prev is not None))

def comparison_months(question):
    full=FULL.findall(question)
    if len(full)==2:
        return [month_period(*x) for x in full]
    if len(full)>2:
        raise CXComparisonRejected('Specify exactly two purchase months')
    shared=SHARED_YEAR.findall(question)
    if len(full)==1 and len(shared)==1:
        m1,m2,y=shared[0]
        return [month_period(m1,y),month_period(m2,y)]
    raise CXComparisonRejected('Specify two explicit purchase months and year; no baseline is assumed')

def metric_for_comparison(question,prev):
    m,reason=resolve_metric(question,prev)
    if m in METRICS:return m
    if reason in ('CUSTOMER_ORDER_GRAIN_AMBIGUITY','INVESTIGATION_NOT_SUPPORTED'):
        raise CXComparisonRejected(reason)
    if re.search(r'\b(satisfaction|happy|customer happiness)\b',question,re.I):return 'average_review_score'
    if prev is not None and not CX_TERMS.search(question):return prev.metric_id
    raise CXComparisonRejected('Specify a registered customer-satisfaction metric')

async def compare(question,previous,reader):
    try:
        p1,p2=comparison_months(question)
        if p1==p2:raise CXComparisonRejected('Comparison months must be different')
        # Preserve user order: 'from May to June' means May before June.
        if date.fromisoformat(p1[0])>=date.fromisoformat(p2[0]):
            raise CXComparisonRejected('Provide earlier month first and later month second')
        metric=metric_for_comparison(question,previous)
    except CXComparisonRejected as exc:
        return {'route':'customer_satisfaction','status':'NEEDS_CLARIFICATION','executable':False,'reason':str(exc),'causal_claim':False},previous
    before=await measure(metric,*p1,reader)
    after=await measure(metric,*p2,reader)
    if any(x.get('source')!=before['source'] or x.get('policy')!=before['policy'] or x.get('time_basis')!=before['time_basis'] or x.get('unit')!=before['unit'] or x.get('metric_id')!=metric for x in (before,after)):
        raise CXComparisonRejected('INCOMPATIBLE_METRIC_CONTRACTS')
    a,b=Decimal(before['value']),Decimal(after['value'])
    delta=b-a
    out={'route':'customer_satisfaction','status':'COMPARISON_MEASURED_WITH_SCOPE_LIMITS','executable':True,
        'metric_id':metric,'before':before,'after':after,'delta':str(delta),
        'delta_unit':'percentage_points' if before['unit']=='percent' else before['unit'],
        'direction':'INCREASED' if delta>0 else 'DECREASED' if delta<0 else 'UNCHANGED',
        'causal_claim':False,'limitations':['Two purchase-month populations may differ in composition',
        'Period coverage is nonempty but continuous coverage is not certified',
        'A difference in review scores or rates does not establish a causal mechanism']}
    return out,CXContext(metric,*p2)

class CXComparisonSession(CXSession):
    async def dispatch(self,question,prior_dispatch,router,finance,finance_reader,graph,planner,graph_reader,investigation):
        prev=self.customer_satisfaction if self.active_domain=='customer_satisfaction' else None
        if comparison_candidate(question,prev):
            result,updated=await compare(question,prev,finance_reader)
            if result['executable']:
                self.customer_satisfaction=updated
                self.active_domain='customer_satisfaction'
            return result
        return await super().dispatch(question,prior_dispatch,router,finance,finance_reader,graph,planner,graph_reader,investigation)
