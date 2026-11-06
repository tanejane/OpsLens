"""Bounded Gemini semantic grounding for approved satisfaction metrics.

Intent discovery cannot authorize SQL. This module only yields a catalogued
metric and explicit month, then delegates to the 4C.11 governed executor.
"""
from __future__ import annotations
from dataclasses import dataclass
from datetime import date
import re
from agent.phase4c11_satisfaction import METRICS, measure

MONTHS={name.lower():n for n,name in enumerate(('January','February','March','April','May','June','July','August','September','October','November','December'),1)}
MONTH_RX=re.compile(r'\b('+'|'.join(MONTHS)+r')\s+(20\d{2})\b',re.I)
CX_TERMS=re.compile(r'\b(review(?:s|ed)?|rating(?:s)?|satisfaction|customer happiness|happy customers|unhappy customers|bad feedback|low.rating)\b',re.I)
DEICTIC=re.compile(r'^\s*(?:what|how)\s+about\s+(?:that|this|it|those)\s*[?.!]?\s*$',re.I)
PERIOD_FOLLOWUP=re.compile(r'^\s*(?:what|how)\s+about\s+('+'|'.join(MONTHS)+r')\s+(20\d{2})\s*[?.!]?\s*$',re.I)
METRIC_FOLLOWUP=re.compile(r'^\s*(?:and\s+)?(?:the\s+)?(?:bad|low)\s+(?:review|rating)\s+rate\s*[?.!]?\s*$',re.I)

@dataclass(frozen=True)
class CXContext:
    metric_id:str
    start:str
    end:str

class CXGroundingRejected(ValueError):pass

def month_period(month:str,year:str):
    y=int(year);m=MONTHS[month.lower()]
    start=date(y,m,1)
    end=date(y+1,1,1) if m==12 else date(y,m+1,1)
    return start.isoformat(),end.isoformat()

def candidate(question:str, previous:CXContext|None)->bool:
    if CX_TERMS.search(question):return True
    if previous and (PERIOD_FOLLOWUP.fullmatch(question) or METRIC_FOLLOWUP.fullmatch(question) or DEICTIC.fullmatch(question)):
        return True
    return False

def resolve_metric(text:str,prev:CXContext|None):
    t=text.lower()
    if re.search(r'\bwhy\b|\bcaus(?:e|ed)|\breason(?:s)?\b|\bdriv(?:e|ers)\b',t):
        return None,'INVESTIGATION_NOT_SUPPORTED'
    if re.search(r'\bcustomer(?:s)?\s+(?:left|submitted|wrote)\s+reviews\b|\bhow\s+many\s+customers\b',t):
        return None,'CUSTOMER_ORDER_GRAIN_AMBIGUITY'
    if re.search(r'\b(?:low|bad|poor|negative)\s+(?:review|rating)|\blow.rating\b',t):return 'low_rating_rate',None
    if re.search(r'\bcoverage\b|\bpercentage\s+reviewed\b|\bpercent\s+of\s+orders\s+(?:with|that\s+have)\s+reviews\b',t):return 'review_coverage',None
    if re.search(r'\bhow\s+many\s+(?:reviewed\s+orders|orders\s+(?:received|with|had)\s+reviews)\b|\breviewed.order\s+count\b',t):return 'reviewed_order_count',None
    if re.search(r'\b(?:average|mean)\s+(?:review|rating|satisfaction)|\bsatisfaction\s+(?:score|rating)\b|\bhow\s+happy\b',t):return 'average_review_score',None
    if prev and (PERIOD_FOLLOWUP.fullmatch(text) or DEICTIC.fullmatch(text)):
        return prev.metric_id,None
    return None,'METRIC_UNCLEAR'

def ground(question:str,prev:CXContext|None):
    if DEICTIC.fullmatch(question):return None,'NEEDS_CLARIFICATION','Please specify a metric or a month.'
    if re.search(r'\bcompare\b|\bversus\b|\bvs\.?\b|\bfrom\s+\w+\s+20\d{2}\s+to\b|\bdid\s+.*\b(increase|decrease|drop|rise|fall)\b',question,re.I):
        return None,'NOT_YET_SUPPORTED','Satisfaction period comparisons are not yet connected; use a single month.'
    metric,problem=resolve_metric(question,prev)
    if problem:return None,'NEEDS_CLARIFICATION' if problem in ('METRIC_UNCLEAR','CUSTOMER_ORDER_GRAIN_AMBIGUITY') else 'NOT_YET_SUPPORTED',problem
    found=MONTH_RX.findall(question)
    if len(found)>1:return None,'NOT_YET_SUPPORTED','Only one purchase month is supported.'
    if found:start,end=month_period(*found[0])
    elif prev and METRIC_FOLLOWUP.fullmatch(question):start,end=prev.start,prev.end
    else:return None,'NEEDS_CLARIFICATION','Specify a purchase month and year; no period has been assumed.'
    return (metric,start,end),None,None

async def execute_cx(question,prev,reader):
    args,status,reason=ground(question,prev)
    if not args:return {'route':'customer_satisfaction','status':status,'executable':False,'reason':reason,'causal_claim':False},prev
    metric,start,end=args
    result=await measure(metric,start,end,reader)
    return {'route':'customer_satisfaction','status':result['status'],'executable':True,'evidence':result,'causal_claim':False},CXContext(metric,start,end)

class CXSession:
    """Separate context so CX follow-ups never overwrite finance/graph memory."""
    def __init__(self,unified_state):
        self.unified_state=unified_state
        self.customer_satisfaction=None
        self.active_domain=None
    async def dispatch(self,question,prior_dispatch,router,finance,finance_reader,graph,planner,graph_reader,investigation):
        prior=self.customer_satisfaction if self.active_domain=="customer_satisfaction" else None
        if candidate(question,prior):
            result,updated=await execute_cx(question,prior,finance_reader)
            if result['executable']:
                self.customer_satisfaction=updated
                self.active_domain="customer_satisfaction"
            return result
        result,new_state=await prior_dispatch(question,self.unified_state,router,finance,finance_reader,graph,planner,graph_reader,investigation)
        self.unified_state=new_state
        if isinstance(result,dict) and result.get("executable") and result.get("route") in ("finance_measure","finance_compare","graph_analytics","investigation"):
            self.active_domain=result["route"]
        return result
