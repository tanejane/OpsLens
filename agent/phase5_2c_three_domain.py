"""Bounded finance + delivery + satisfaction investigation. No new SQL permissions.

Finance premise comes from existing governed Phase4C7. Operational comparisons
are descriptive and do not prove order-level linkage or causation.
"""
from __future__ import annotations
from datetime import date
from copy import deepcopy
from decimal import Decimal, InvalidOperation
import re

class ThreeDomainRejected(ValueError): pass

MONTHS={m.lower():i for i,m in enumerate(('January','February','March','April','May','June','July','August','September','October','November','December'),1)}
PAIR=re.compile(r'\b('+'|'.join(MONTHS)+r')\s+(20\d{2})\b',re.I)
BLOCK=re.compile(r'(;|--|/\*|\*/|\b(?:drop|delete|insert|update|alter|grant|revoke|stockout|inventory)\b|ignore\s+previous\s+instructions)',re.I)

def periods_of(question):
    if not isinstance(question,str) or not 1<=len(question.strip())<=500 or BLOCK.search(question):raise ThreeDomainRejected('UNSAFE_REQUEST')
    found=PAIR.findall(question)
    if len(found)!=2:raise ThreeDomainRejected('REQUIRE_TWO_EXPLICIT_MONTH_YEAR_PAIRS')
    p=[]
    for mon,year in found:
        y=int(year);m=MONTHS[mon.lower()]
        if not 2016<=y<=2026:raise ThreeDomainRejected('UNSUPPORTED_PERIOD')
        a=date(y,m,1);b=date(y+1,1,1) if m==12 else date(y,m+1,1)
        p.append([a.isoformat(),b.isoformat()])
    if p[0][0]>=p[1][0]:raise ThreeDomainRejected('PERIODS_NOT_EARLIEST_FIRST')
    return p

def dec(x):
    if x is None or isinstance(x,bool):raise ThreeDomainRejected('INVALID_NUMBER')
    try:v=Decimal(str(x))
    except (InvalidOperation,TypeError,ValueError) as e:raise ThreeDomainRejected('INVALID_NUMBER') from e
    if not v.is_finite():raise ThreeDomainRejected('NONFINITE_NUMBER')
    return v

def combine(question, finance, operational):
    periods=periods_of(question)
    if not isinstance(finance,dict) or finance.get('route')!='investigation' or finance.get('executable') is not True or finance.get('causal_claim') is not False:
        raise ThreeDomainRejected('FINANCE_NOT_GOVERNED')
    if finance.get('periods')!={'before':periods[0],'after':periods[1]}:raise ThreeDomainRejected('FINANCE_PERIOD_MISMATCH')
    premise=finance.get('premise')
    if not isinstance(premise,dict) or type(premise.get('divergence_confirmed')) is not bool:raise ThreeDomainRejected('FINANCE_PREMISE_NOT_VERIFIED')
    if finance.get('status') not in ('EVIDENCE_RANKED_NOT_CAUSAL','PREMISE_NOT_CONFIRMED','PARTIAL_EVIDENCE_BUDGET','INSUFFICIENT_GOVERNED_EVIDENCE'):
        raise ThreeDomainRejected('FINANCE_STATUS_NOT_ACCEPTED')
    if premise['divergence_confirmed']:
        if premise.get('revenue_increased') is not True or premise.get('contribution_profit_decreased') is not True:raise ThreeDomainRejected('FINANCE_PREMISE_INCONSISTENT')
    dr=dec(premise.get('revenue_delta'));dp=dec(premise.get('contribution_profit_delta'))
    if premise['divergence_confirmed'] and not (dr>0 and dp<0):raise ThreeDomainRejected('FINANCE_DELTA_DIRECTION_INCONSISTENT')
    if finance.get('hypothesis_evaluation') is not None:
        h=finance['hypothesis_evaluation']
        if not isinstance(h,dict) or h.get('status')!='EVIDENCE_RANKED_NOT_CAUSAL' or h.get('causal_claim') is not False:raise ThreeDomainRejected('FINANCE_HYPOTHESIS_UNVERIFIED')
    if not isinstance(operational,dict) or operational.get('status')!='CROSS_DOMAIN_DESCRIPTIVE_COMPARISON' or operational.get('causal_claim') is not False or operational.get('approved_for_mcp') is not False:
        raise ThreeDomainRejected('OPERATIONAL_CONTRACT_NOT_VERIFIED')
    if operational.get('periods')!={'before':periods[0],'after':periods[1]}:raise ThreeDomainRejected('OPERATIONAL_PERIOD_MISMATCH')
    if operational.get('domains')!=['delivery_operations','customer_satisfaction'] or operational.get('evidence_relation')!='SAME_PURCHASE_MONTH_COHORT_COUNT_NOT_ORDER_LEVEL_LINKAGE':
        raise ThreeDomainRejected('OPERATIONAL_SCOPE_INCONSISTENT')
    changes=operational.get('metric_changes')
    if not isinstance(changes,dict) or set(changes)!={'late_delivery_rate','average_review_score','low_rating_rate'}:raise ThreeDomainRejected('OPERATIONAL_METRIC_SET_INVALID')
    for key,v in changes.items():
        if not isinstance(v,dict):raise ThreeDomainRejected('OPERATIONAL_INVALID_CHANGE')
        if dec(v.get('after'))-dec(v.get('before')) != dec(v.get('delta')):raise ThreeDomainRejected('OPERATIONAL_DELTA_MISMATCH')
    if operational.get('directional_pattern') not in ('COINCIDENT_IMPROVEMENT','COINCIDENT_DETERIORATION','MIXED_OR_NO_CONSISTENT_DIRECTION'):
        raise ThreeDomainRejected('OPERATIONAL_PATTERN_INVALID')
    return {'route':'three_domain_investigation','status':'THREE_DOMAIN_DESCRIPTIVE_EVIDENCE',
      'executable':True,'periods':{'before':periods[0],'after':periods[1]},
      'domains':['finance','delivery_operations','customer_satisfaction'],
      'domain_results':{'finance':deepcopy(finance),'operations':deepcopy(operational)},
      'financial_premise':{'divergence_confirmed':premise['divergence_confirmed'],'revenue_delta':str(dr),'contribution_profit_delta':str(dp)},
      'financial_evidence_status':finance['status'],
      'accounting_hypotheses':finance.get('hypothesis_evaluation',{}).get('hypotheses',[]) if premise['divergence_confirmed'] else [],
      'operational_changes':changes,'operational_pattern':operational['directional_pattern'],
      'cohort_orders':operational['cohort_orders'],
      'evidence_relation':'PERIOD_ALIGNED_SEPARATE_FINANCIAL_AND_OPERATIONAL_POPULATIONS',
      'conclusions':['Finance premise verified against its governed population' if premise['divergence_confirmed'] else 'Financial divergence premise not confirmed',
                     'Delivery and satisfaction changes are observed within matched purchase-month cohort counts; they are not causal explanations of profit'],
      'next_validations':['Independently verify exact order-ID sets for the requested periods before claiming matching order membership',
                          'Verify operational mechanisms and cost allocation with separately approved linkage and confounder controls',
                          'Validate modeled finance cost inputs against independent source records'],
      'limitations':['Finance excludes certain orders; operational populations differ and cannot be silently equated',
                     'An exact order-ID audit for the requested periods has not been attached to this report',
                     'Metric-specific delivery and review eligibility denominators differ',
                     'Financial costs or delivery/review adjustments can be modeled; descriptive comparisons do not prove causal impact'],
      'causal_claim':False,'approved_for_mcp':False,'inventory_claim_allowed':False,
      'tool_trace':[{'capability':'existing_bounded_finance_investigator','status':finance['status']},
                    {'capability':'governed_delivery_and_review_metrics','status':operational['status']} ]}

async def investigate(question,reader,finance_investigator):
    """Finance and operational tools remain independently governed; reject all partial tool failures."""
    periods=periods_of(question)
    # A canonical finance question preserves explicit compared dates and premise verification.
    first=date.fromisoformat(periods[0][0]);second=date.fromisoformat(periods[1][0]);mn=list(MONTHS)
    baseline=f'{mn[first.month-1].capitalize()} {first.year}'
    current=f'{mn[second.month-1].capitalize()} {second.year}'
    finance_question=f'Why did revenue increase while profit decreased in {current} compared with {baseline}?'
    finance=await finance_investigator(finance_question,reader)
    if not isinstance(finance,dict) or finance.get('route')!='investigation' or finance.get('executable') is not True:raise ThreeDomainRejected('FINANCE_INVESTIGATION_NOT_EXECUTED')
    from agent.phase4c15_delivery import measure as delivery_measure
    from agent.phase4c11_satisfaction import measure as satisfaction_measure
    measurements=[]
    for start,end in periods:
        measurements.append({'late_delivery_rate':await delivery_measure('late_delivery_rate',start,end,reader),
                             'average_review_score':await satisfaction_measure('average_review_score',start,end,reader),
                             'low_rating_rate':await satisfaction_measure('low_rating_rate',start,end,reader)})
    from agent.phase5_2_multidomain import synthesize as synthesize_operational
    operational=synthesize_operational(periods,measurements)
    return combine(question,finance,operational)
