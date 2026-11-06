"""Conservative delivery NLP router over audited Phase 4C.15 metric executor.
No LLM-authored SQL; existing finance/graph/CX routing is retained.
"""
from dataclasses import dataclass
import re
from agent.phase4c12_cx_nlp import MONTHS, month_period
from agent.phase4c13_cx_compare import CXComparisonSession
from agent.phase4c15_delivery import measure

M='|'.join(MONTHS)
MONTH=re.compile(r'\b('+M+r')\s+(20\d{2})\b',re.I)
DELIVERY=re.compile(r'\b(deliver(?:y|ies|ed)?|shipping|shipment|late.orders?|late.delivery|arriv(?:e|ed|al)|on.time)\b',re.I)
FOLLOW_PERIOD=re.compile(r'^\s*(?:what|how)\s+about\s+('+M+r')\s+(20\d{2})\s*[?.!]?\s*$',re.I)
FOLLOW_RATE=re.compile(r'^\s*(?:and\s+)?(?:the\s+)?(?:late.delivery|lateness)\s+rate\s*[?.!]?\s*$',re.I)
COMPARE=re.compile(r'\b(?:compare|versus|between|vs\.?|difference|trend|improv(?:e|ed)|worsen(?:ed)?|increase(?:d)?|decrease(?:d)?|drop(?:ped)?|from\s+\w+\s+20\d{2}\s+to)\b',re.I)

@dataclass(frozen=True)
class DeliveryContext:
    metric_id:str
    start:str
    end:str

def delivery_candidate(question,active_delivery):
    return bool(DELIVERY.search(question) or (active_delivery and (FOLLOW_PERIOD.fullmatch(question) or FOLLOW_RATE.fullmatch(question))))

def _blocked(status,reason):
    return {'route':'delivery_operations','status':status,'executable':False,'reason':reason,'causal_claim':False}

def ground_delivery(question,prev):
    t=question.lower()
    if re.search(r'\bwhy\b|\bcause(?:s|d)?\b|\breason\b|\bassociated\b|\bimpact\b',t):
        return None,_blocked('NOT_YET_SUPPORTED','Delivery diagnosis and cross-domain relationships are not yet connected')
    if COMPARE.search(question):
        return None,_blocked('NOT_YET_SUPPORTED','Delivery period comparisons are not yet connected')
    # Ambiguous population: customer count cannot be treated as order count.
    if re.search(r'\bhow\s+many\s+customers\b',t):
        return None,_blocked('NEEDS_CLARIFICATION','CUSTOMER_ORDER_GRAIN_AMBIGUITY')
    if re.search(r'\b(?:evidence|date|timestamp)\s+coverage\b|\bdelivery\s+coverage\b|\bpercent(?:age)?\s+of\s+orders\s+with\s+(?:delivery|complete)\s+(?:data|timestamps|dates)\b',t):
        metric='delivery_evidence_coverage'
    elif (re.search(r'\b(?:how\s+many|number\s+of|count\s+of)\s+(?:orders\s+(?:were\s+)?)?deliver(?:ed|ies)\b|\bdelivered\s+order\s+count\b',t) and not re.search(r'\blate\b',t)):
        metric='delivered_order_count'
    elif re.search(r'\b(?:average|mean|how\s+long)\b|\bduration\b|\bdelivery\s+time\b|\bdays\s+to\s+deliver\b',t):
        metric='average_delivery_days'
    elif re.search(r'\b(?:late|lateness|on.time|delayed?)\b',t) or FOLLOW_RATE.fullmatch(question):
        metric='late_delivery_rate'
    elif prev and FOLLOW_PERIOD.fullmatch(question):
        metric=prev.metric_id
    else:
        return None,_blocked('NEEDS_CLARIFICATION','Specify late-delivery rate, average duration, delivered orders, or delivery evidence coverage')
    matches=MONTH.findall(question)
    if len(matches)>1:return None,_blocked('NEEDS_CLARIFICATION','Specify one purchase month, not multiple months')
    if matches: start,end=month_period(*matches[0])
    elif prev and FOLLOW_RATE.fullmatch(question):start,end=prev.start,prev.end
    else:return None,_blocked('NEEDS_CLARIFICATION','Specify purchase month and year; no date inferred')
    return (metric,start,end),None

class DeliveryNLPSession(CXComparisonSession):
    def __init__(self,unified_state):
        super().__init__(unified_state)
        self.delivery_context=None

    async def dispatch(self,question,prior_dispatch,router,finance,finance_reader,graph,planner,graph_reader,investigation):
        prev=self.delivery_context if self.active_domain=='delivery_operations' else None
        if delivery_candidate(question,prev):
            args,blocked=ground_delivery(question,prev)
            if blocked:return blocked
            metric,start,end=args
            evidence=await measure(metric,start,end,finance_reader)
            self.delivery_context=DeliveryContext(metric,start,end)
            self.active_domain='delivery_operations'
            return {'route':'delivery_operations','status':evidence['status'],'executable':True,'evidence':evidence,'causal_claim':False}
        return await super().dispatch(question,prior_dispatch,router,finance,finance_reader,graph,planner,graph_reader,investigation)
