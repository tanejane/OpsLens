"""Offline deterministic tests. Real MCP access must be tested separately."""
import asyncio
from decimal import Decimal
from agent.phase4c13_cx_compare import compare,comparison_candidate,comparison_months, CXComparisonRejected
from agent.phase4c12_cx_nlp import CXContext
from agent.phase4c11_satisfaction import compile_metric

N=0
def check(name,ok):
 global N
 assert ok,name
 N+=1;print('PASS:',name)

async def main():
 calls=[]
 async def reader(sql,purpose):
  calls.append(sql)
  ismay="DATE '2018-05-01'" in sql
  reviewed=6839 if ismay else 6141
  eligible=6873 if ismay else 6167
  low=814 if ismay else 675
  average='4.19403421552858605059' if ismay else '4.25362318840579710145'
  return {'eligible_orders':eligible,'reviewed_orders':reviewed,'low_rating_orders':low,'multi_review_orders':9 if ismay else 6,
   'average_score':average,'low_rating_rate_pct':str(Decimal(low)*100/Decimal(reviewed)),
   'review_coverage_pct':str(Decimal(reviewed)*100/Decimal(eligible)),
   'distinct_orders':eligible,'invalid_scores':0,'invalid_flags':0}
 q='Did satisfaction drop from May to June 2018?'
 check('candidate satisfaction',comparison_candidate(q,None))
 check('period grounding', comparison_months(q)==[('2018-05-01','2018-06-01'),('2018-06-01','2018-07-01')])
 out,ctx=await compare(q,None,reader)
 check('comparison executable',out['executable'] and out['status']=='COMPARISON_MEASURED_WITH_SCOPE_LIMITS')
 check('score positive',Decimal(out['delta'])>0 and out['direction']=='INCREASED')
 check('same contracts',out['before']['policy']==out['after']['policy'])
 check('period context updated',ctx.start=='2018-06-01')
 check('two approved queries',len(calls)==2 and all('semantic.order_review_evidence_v1' in s for s in calls))
 prev=CXContext('low_rating_rate','2018-05-01','2018-06-01')
 out,ctx=await compare('Compare May and June 2018',prev,reader)
 check('followup metric',out['metric_id']=='low_rating_rate')
 check('rate units',out['delta_unit']=='percentage_points' and Decimal(out['delta'])<0)
 out,_=await compare('Compare bad review rate in May 2018 versus June 2018',None,reader)
 check('explicit rate',out['metric_id']=='low_rating_rate')
 k=len(calls)
 for name,q in [('missing year','Compare satisfaction May to June'),('missing first month','Compare satisfaction in June 2018'),('reverse date','Compare satisfaction June to May 2018'),('same period','Compare satisfaction May and May 2018'),('no score assumption','Compare reviews May and June 2018'),('three months','Compare satisfaction May 2018 June 2018 July 2018'),('customer ambiguity','Compare how many customers left reviews May to June 2018')]:
  r,c=await compare(q,None,reader)
  check(name,not r['executable'] and c is None)
 check('clarifications do not query',len(calls)==k)
 async def denied(sql,purpose):raise PermissionError('Denied')
 try:await compare(q:='Compare satisfaction May to June 2018',None,denied)
 except PermissionError:check('MCP failure fail closed',True)
 else:check('MCP failure fail closed',False)
 check('metric SQL fixed',compile_metric('average_review_score','2018-05-01','2018-06-01')['source']=='semantic.order_review_evidence_v1')
 print(f'Checks passed: {N}/{N}')
if __name__=='__main__':asyncio.run(main())
