"""Governed delivery purchase-month comparisons: no new SQL contracts/permissions."""
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
import re
from agent.phase4c15_delivery import METRICS, measure, DeliveryRejected
from agent.phase4c16_delivery_nlp import DeliveryNLPSession, DeliveryContext, DELIVERY, MONTH, COMPARE, M, month_period

SHARED_YEAR = re.compile(r'\b('+M+r')\s+(?:to|and|vs\.?|versus|through)\s+('+M+r')\s+(20\d{2})\b', re.I)
STRONG_COMPARE = re.compile(r'\b(?:compare|comparison|versus|vs\.?|between|from\b.+\bto|did\b.+\b(?:drop|fall|rise|increase|decrease|improve|worsen)|changed?\b|difference|trend)\b',re.I)

class DeliveryComparisonRejected(ValueError): pass

# An explicit new subject must override the delivery context.  Without this,
# a generic comparison verb (e.g. "decreased") can hijack a finance question
# after the user has just asked about delivery.  We only retain delivery for
# genuinely elliptical comparisons with no competing named domain.
EXPLICIT_OTHER_DOMAIN = re.compile(
    r'\b(?:revenue|reveneu|revnue|profit|profitt|margin|cogs|costs?|'
    r'gmv|sales|customer\s+satisfaction|reviews?|ratings?|'
    r'product\s+categor(?:y|ies)|units\s+sold)\b', re.I)

def is_comparison(question,previous):
    if not isinstance(question, str) or not STRONG_COMPARE.search(question):
        return False
    if EXPLICIT_OTHER_DOMAIN.search(question):
        return False
    if DELIVERY.search(question):
        return True
    return previous is not None


def periods(question):
    full = MONTH.findall(question)
    if len(full)==2:
        pairs=[month_period(*m) for m in full]
    elif len(full)==1:
        shared=SHARED_YEAR.findall(question)
        if len(shared)!=1:raise DeliveryComparisonRejected('Specify two explicit purchase months; no baseline inferred')
        a,b,y=shared[0];pairs=[month_period(a,y),month_period(b,y)]
    else:raise DeliveryComparisonRejected('Specify exactly two explicit purchase months')
    if date.fromisoformat(pairs[0][0])>=date.fromisoformat(pairs[1][0]):
        raise DeliveryComparisonRejected('Specify earlier month first and later month second')
    return pairs

def metric(question,previous):
    t=question.lower()
    if re.search(r'\b(?:why|cause|caused|reasons?|impact|associated)\b',t):
        raise DeliveryComparisonRejected('Operational causation and delivery-review relationships are not yet validated')
    if re.search(r'\bhow\s+many\s+customers\b',t):raise DeliveryComparisonRejected('CUSTOMER_ORDER_GRAIN_AMBIGUITY')
    if re.search(r'\b(?:evidence|timestamp|date)\s+coverage\b|\bdelivery\s+coverage\b',t):return 'delivery_evidence_coverage'
    if re.search(r'\b(?:how\s+many|number\s+of|count\s+of)\s+(?:orders\s+(?:were\s+)?)?delivered\b|\bdelivered\s+order\s+count\b',t) and 'late' not in t:return 'delivered_order_count'
    if re.search(r'\b(?:average|mean|how\s+long)\b|\bduration\b|\bdelivery\s+time\b|\bdays\s+to\s+deliver\b',t):return 'average_delivery_days'
    if re.search(r'\b(?:late|lateness|on.time|delayed?)\b',t):return 'late_delivery_rate'
    if previous:return previous.metric_id
    raise DeliveryComparisonRejected('Specify the registered delivery metric to compare')

async def compare_delivery(question,previous,reader):
    try:
        p=periods(question)
        requested_metric=metric(question,previous)
        if requested_metric not in METRICS:raise DeliveryComparisonRejected('Unsupported delivery metric')
    except (DeliveryComparisonRejected, ValueError) as exc:
        return {'route':'delivery_operations','status':'NEEDS_CLARIFICATION','executable':False,'reason':str(exc),'causal_claim':False},previous
    before=await measure(requested_metric,*p[0],reader)
    after=await measure(requested_metric,*p[1],reader)
    for field in ('metric_id','unit','source','policy','time_basis'):
        if before.get(field)!=after.get(field):raise DeliveryComparisonRejected('INCOMPATIBLE_DELIVERY_METRIC_CONTRACTS: '+field)
    if before['metric_id']!=requested_metric or before['period']!=list(p[0]) or after['period']!=list(p[1]):
        raise DeliveryComparisonRejected('INCOMPATIBLE_DELIVERY_PERIODS')
    a,b=Decimal(before['value']),Decimal(after['value'])
    diff=b-a
    return ({'route':'delivery_operations','status':'COMPARISON_MEASURED_WITH_SCOPE_LIMITS','executable':True,
             'metric_id':requested_metric,'before':before,'after':after,'delta':str(diff),
             'delta_unit':'percentage_points' if before['unit']=='percent' else before['unit'],
             'direction':'INCREASED' if diff>0 else 'DECREASED' if diff<0 else 'UNCHANGED',
             'causal_claim':False,'limitations':['Different purchase-month order cohorts may have different composition',
               'Missing actual delivery timestamps are excluded from lateness and duration denominators',
               'Effective delivery timestamps may include modeled incident adjustments',
               'Descriptive changes do not establish causality or continuous source coverage']},
            DeliveryContext(requested_metric,*p[1]))

class DeliveryComparisonSession(DeliveryNLPSession):
    async def dispatch(self,question,prior_dispatch,router,finance,finance_reader,graph,planner,graph_reader,investigation):
        previous=self.delivery_context if self.active_domain=='delivery_operations' else None
        if is_comparison(question,previous):
            out,updated=await compare_delivery(question,previous,finance_reader)
            if out['executable']:
                self.delivery_context=updated
                self.active_domain='delivery_operations'
            return out
        return await super().dispatch(question,prior_dispatch,router,finance,finance_reader,graph,planner,graph_reader,investigation)
