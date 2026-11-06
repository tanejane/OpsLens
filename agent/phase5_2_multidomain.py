"""Phase 5.2: bounded delivery + satisfaction two-month investigator.

Uses the pre-existing, governed Phase 4C.15 / 4C.11 MCP metric compilers.
No new SQL grammar, joins, authorizations, causality or LLM-generated plans.
"""
from __future__ import annotations
from datetime import date
from copy import deepcopy
from decimal import Decimal, InvalidOperation
import re
from agent.phase4c15_delivery import measure as delivery_measure
from agent.phase4c11_satisfaction import measure as review_measure

class MultiDomainRejected(ValueError):
    pass

MONTHS = ('January','February','March','April','May','June','July','August','September','October','November','December')
MONTH_MAP = {m.lower():i+1 for i,m in enumerate(MONTHS)}
EXPLICIT = re.compile(r'\b('+ '|'.join(MONTHS) +r')\s+(20\d{2})\b', re.I)
SUPPORTED = re.compile(r'\b(?:delivery|deliveries|delays?|late|lateness)\b',re.I)
REVIEWS = re.compile(r'\b(?:reviews?|ratings?|satisfaction|score)\b',re.I)
UNSUPPORTED = re.compile(r'\b(?:why|cause|caused|causing|explain|impact|driv(?:e|en)|responsible|stockout|inventory)\b',re.I)
INJECTION = re.compile(r'(;|--|/\*|\*/|\b(?:drop|delete|insert|update|alter|grant|revoke)\b|ignore\s+(?:all\s+)?previous\s+instructions)',re.I)

def parse_request(question:str):
    """Accept explicit two-cohort delivery-and-satisfaction comparisons only."""
    if not isinstance(question,str) or not 1 <= len(question.strip()) <= 500 or INJECTION.search(question):
        raise MultiDomainRejected('INVALID_OR_UNSAFE_QUESTION')
    if UNSUPPORTED.search(question):
        raise MultiDomainRejected('CAUSAL_OR_UNSUPPORTED_INTENT')
    if not SUPPORTED.search(question) or not REVIEWS.search(question):
        raise MultiDomainRejected('REQUIRE_EXPLICIT_DELIVERY_AND_SATISFACTION')
    matches=EXPLICIT.findall(question)
    if len(matches)!=2:
        raise MultiDomainRejected('REQUIRE_TWO_EXPLICIT_MONTH_YEAR_PAIRS')
    ps=[]
    for month,year in matches:
        y=int(year); m=MONTH_MAP[month.lower()]
        if y<2016 or y>2026:raise MultiDomainRejected('UNSUPPORTED_PERIOD')
        start=date(y,m,1)
        end=date(y+1,1,1) if m==12 else date(y,m+1,1)
        ps.append((start.isoformat(),end.isoformat()))
    if ps[0][0]>=ps[1][0]:raise MultiDomainRejected('REQUIRE_EARLIER_THEN_LATER')
    return ps

def _num(v):
    if isinstance(v,bool) or v is None:raise MultiDomainRejected('INVALID_MEASUREMENT')
    try:d=Decimal(str(v))
    except (InvalidOperation,TypeError,ValueError) as exc:raise MultiDomainRejected('INVALID_MEASUREMENT') from exc
    if not d.is_finite():raise MultiDomainRejected('INVALID_MEASUREMENT')
    return d

def _check_measure(result, metric, source, unit, start, end):
    if not isinstance(result,dict) or result.get('status')!='MEASURED_WITH_SCOPE_LIMITS' or result.get('metric_id')!=metric or result.get('source')!=source or result.get('unit')!=unit or result.get('period')!=[start,end] or result.get('time_basis')!='order_purchase_time' or result.get('causal_claim') is not False:
        raise MultiDomainRejected('INCONSISTENT_METRIC_CONTRACT')
    p=result.get('population')
    if not isinstance(p,dict):raise MultiDomainRejected('MISSING_POPULATION')
    n=p.get('eligible_orders')
    if type(n) is not int or n<=0:raise MultiDomainRejected('INVALID_COHORT_COUNT')
    d=_num(result.get('value'))
    if unit=='percent' and not 0<=d<=100:raise MultiDomainRejected('INVALID_RATE')
    if unit=='score_1_to_5' and not 1<=d<=5:raise MultiDomainRejected('INVALID_SCORE')
    return d,n

def synthesize(periods, measurements):
    """Independently check domain consistency; descriptive only."""
    if not isinstance(periods,list) or len(periods)!=2 or not isinstance(measurements,list) or len(measurements)!=2:
        raise MultiDomainRejected('INVALID_PERIODS_OR_MEASUREMENTS')
    periods_check=[]; cohorts=[]
    descriptors=(('late_delivery_rate','semantic.order_delivery_evidence_v1','percent'),
                 ('average_review_score','semantic.order_review_evidence_v1','score_1_to_5'),
                 ('low_rating_rate','semantic.order_review_evidence_v1','percent'))
    for idx, pair in enumerate(periods):
        if not isinstance(pair,(list,tuple)) or len(pair)!=2:raise MultiDomainRejected('INVALID_PERIOD')
        start,end=pair
        # Validate exact one-calendar-month intervals (do not trust caller-supplied boundaries).
        try:
            d=date.fromisoformat(start);e=date.fromisoformat(end)
        except (ValueError,TypeError) as exc:raise MultiDomainRejected('INVALID_PERIOD') from exc
        if d.day!=1 or e!=(date(d.year+1,1,1) if d.month==12 else date(d.year,d.month+1,1)):
            raise MultiDomainRejected('NON_MONTH_PERIOD')
        bucket=measurements[idx]
        if not isinstance(bucket,dict) or set(bucket)!=set(m[0] for m in descriptors):
            raise MultiDomainRejected('INCOMPLETE_DOMAIN_MEASUREMENTS')
        vals={}; ns={}
        for metric,source,unit in descriptors:
            v,n=_check_measure(bucket[metric],metric,source,unit,start,end)
            vals[metric]=v;ns[metric]=n
        if len(set(ns.values()))!=1:
            raise MultiDomainRejected('CROSS_DOMAIN_COHORT_MISMATCH')
        if bucket['average_review_score']['population']!=bucket['low_rating_rate']['population']:
            raise MultiDomainRejected('REVIEW_POPULATION_DISAGREEMENT')
        periods_check.append(vals);cohorts.append(ns['late_delivery_rate'])
    if periods[0][0]>=periods[1][0]:raise MultiDomainRejected('NONCHRONOLOGICAL_PERIODS')
    changes={}
    for metric,unit in (('late_delivery_rate','percentage_points'),('average_review_score','score_points'),('low_rating_rate','percentage_points')):
        before=periods_check[0][metric];after=periods_check[1][metric];delta=after-before
        changes[metric]={'before':str(before),'after':str(after),'delta':str(delta),'delta_unit':unit,
                         'beforeEvidence':deepcopy(measurements[0][metric]),
                         'afterEvidence':deepcopy(measurements[1][metric]),
                         'direction':'INCREASED' if delta>0 else 'DECREASED' if delta<0 else 'UNCHANGED'}
    late=periods_check[1]['late_delivery_rate']-periods_check[0]['late_delivery_rate']
    low=periods_check[1]['low_rating_rate']-periods_check[0]['low_rating_rate']
    score=periods_check[1]['average_review_score']-periods_check[0]['average_review_score']
    if late>0 and low>0 and score<0:pattern='COINCIDENT_DETERIORATION'
    elif late<0 and low<0 and score>0:pattern='COINCIDENT_IMPROVEMENT'
    else:pattern='MIXED_OR_NO_CONSISTENT_DIRECTION'
    return {'route':'multidomain_investigation','status':'CROSS_DOMAIN_DESCRIPTIVE_COMPARISON',
            'executable':True,'periods':{'before':list(periods[0]),'after':list(periods[1])},
            'domains':['delivery_operations','customer_satisfaction'],
            'measurements':deepcopy(measurements),
            'metric_changes':changes,'cohort_orders':{'before':cohorts[0],'after':cohorts[1]},
            'directional_pattern':pattern,'evidence_relation':'SAME_PURCHASE_MONTH_COHORT_COUNT_NOT_ORDER_LEVEL_LINKAGE',
            'hypotheses':[{'hypothesis':'Late deliveries and poorer reviews may co-occur',
                           'disposition':'NOT_TESTED_CAUSALLY',
                           'next_validation':'Use a separately governed order-level delivery-to-review linkage and adjust for confounders'}],
            'limitations':['Order counts agree across governed views, but identical order-id sets were not independently reconciled',
                           'Different purchase-month populations may have different composition',
                           'Review and delivery evidence may include modeled incident adjustments',
                           'No cross-domain join, statistical causal identification, or continuous coverage certification'],
            'causal_claim':False,'approved_for_mcp':False,'inventory_claim_allowed':False}

async def investigate(question, reader):
    """All data access remains within previously approved metric compilers and MCP reader."""
    periods=parse_request(question)
    data=[]
    for start,end in periods:
        data.append({'late_delivery_rate':await delivery_measure('late_delivery_rate',start,end,reader),
                     'average_review_score':await review_measure('average_review_score',start,end,reader),
                     'low_rating_rate':await review_measure('low_rating_rate',start,end,reader)})
    return synthesize(periods,data)
