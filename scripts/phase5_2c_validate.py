"""Deterministic contract regression; no database or API required."""
from copy import deepcopy
from decimal import Decimal
from agent.phase5_2c_three_domain import periods_of,combine,ThreeDomainRejected

P=['2018-02-01','2018-03-01'];Q=['2018-03-01','2018-04-01']
QUESTION='Compare finance, late delivery and review scores from February 2018 to March 2018'

def fixtures():
 f={'route':'investigation','executable':True,'causal_claim':False,'periods':{'before':P,'after':Q},
    'premise':{'divergence_confirmed':True,'revenue_increased':True,'contribution_profit_decreased':True,'revenue_delta':'139034.73','contribution_profit_delta':'-48578.13'},
    'status':'EVIDENCE_RANKED_NOT_CAUSAL','hypothesis_evaluation':{'status':'EVIDENCE_RANKED_NOT_CAUSAL','causal_claim':False,'hypotheses':[{'hypothesis_id':'financial_component:effective_cogs','disposition':'SUPPORTS_PROFIT_PRESSURE'}]}}
 changes={}
 for key,before,after,unit in [('late_delivery_rate','9.00','8.00','percentage_points'),('average_review_score','4.00','4.10','score_points'),('low_rating_rate','11.00','10.00','percentage_points')]:
  changes[key]={'before':before,'after':after,'delta':str(Decimal(after)-Decimal(before)),'delta_unit':unit,'direction':'INCREASED' if Decimal(after)>Decimal(before) else 'DECREASED'}
 o={'status':'CROSS_DOMAIN_DESCRIPTIVE_COMPARISON','causal_claim':False,'approved_for_mcp':False,'periods':{'before':P,'after':Q},'domains':['delivery_operations','customer_satisfaction'],'evidence_relation':'SAME_PURCHASE_MONTH_COHORT_COUNT_NOT_ORDER_LEVEL_LINKAGE','metric_changes':changes,'directional_pattern':'COINCIDENT_IMPROVEMENT','cohort_orders':{'before':6500,'after':7000}}
 return f,o

def run():
 f,o=fixtures();tests=[]
 def check(name,fn,valid=True):
  try:
   result=fn()
   if not valid:raise AssertionError('Unexpected approval')
   tests.append(name)
  except ThreeDomainRejected:
   if valid:raise
   tests.append(name)
 def test_mut(name,target,field,value):
  ff,oo=fixtures();t=ff if target=='f' else oo;t[field]=value
  check(name,lambda:combine(QUESTION,ff,oo),False)
 check('valid compound report',lambda:combine(QUESTION,f,o))
 result=combine(QUESTION,f,o)
 assert result['causal_claim'] is False and result['approved_for_mcp'] is False
 assert result['financial_premise']['divergence_confirmed'] is True
 assert result['evidence_relation']=='PERIOD_ALIGNED_SEPARATE_FINANCIAL_AND_OPERATIONAL_POPULATIONS'
 assert 'not been attached' in result['limitations'][1]
 check('correct dates',lambda:periods_of(QUESTION))
 for name,q in [('missing year','Compare February to March 2018'),('reversed','Compare March 2018 to February 2018'),('single','Compare March 2018'),('SQL injection','Compare February 2018 to March 2018; DROP TABLE orders'),('overlong','x'*501),('empty',''),('nonstr',None),('extra period','Compare January 2018 February 2018 March 2018')]:
  check(name,lambda q=q:periods_of(q),False)
 for name,target,key,value in [('finance wrong route','f','route','delivery_operations'),('finance false executable','f','executable',False),('finance causal','f','causal_claim',True),('finance wrong periods','f','periods',{'before':Q,'after':P}),('finance unknown status','f','status','BYPASSED'),('operational causal','o','causal_claim',True),('operational wrong status','o','status','OK'),('operational mcp flag','o','approved_for_mcp',True),('operational wrong periods','o','periods',{'before':Q,'after':P}),('operational wrong domains','o','domains',['finance','delivery_operations']),('operational wrong evidence','o','evidence_relation','SAME_IDS'),('operational fake pattern','o','directional_pattern','CAUSE'),('missing metrics','o','metric_changes',{}),('finance null premise','f','premise',None)]:
  test_mut(name,target,key,value)
 for name,mut in [('bad money',lambda f,o:f['premise'].__setitem__('revenue_delta','NaN')),('bool money',lambda f,o:f['premise'].__setitem__('revenue_delta',True)),('wrong finance direction',lambda f,o:f['premise'].__setitem__('revenue_delta','-1')),('wrong profit direction',lambda f,o:f['premise'].__setitem__('contribution_profit_delta','1')),('unverified hypothesis',lambda f,o:f['hypothesis_evaluation'].__setitem__('causal_claim',True)),('operational tampered delta',lambda f,o:o['metric_changes']['late_delivery_rate'].__setitem__('delta','0')),('operational missing delta',lambda f,o:o['metric_changes']['low_rating_rate'].pop('delta')),('operational fake value',lambda f,o:o['metric_changes']['low_rating_rate'].__setitem__('after','Infinity')),('premise inconsistent',lambda f,o:f['premise'].__setitem__('revenue_increased',False))]:
  ff,oo=fixtures();mut(ff,oo);check(name,lambda ff=ff,oo=oo:combine(QUESTION,ff,oo),False)
 ff,oo=fixtures();ff['premise']={'divergence_confirmed':False,'revenue_delta':'-30','contribution_profit_delta':'-40'};ff['status']='PREMISE_NOT_CONFIRMED';ff.pop('hypothesis_evaluation');check('false premise reported not explained',lambda:combine(QUESTION,ff,oo))
 print('\n'.join('PASS: '+s for s in tests));print(f'Checks passed: {len(tests)}/{len(tests)}')
if __name__=='__main__':run()
