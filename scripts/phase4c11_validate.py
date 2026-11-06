from agent.phase4c11_satisfaction import compile_metric,validate_metric,ReviewRejected,measure
import asyncio

P=compile_metric('low_rating_rate','2018-06-01','2018-07-01')
R={'eligible_orders':100,'reviewed_orders':80,'low_rating_orders':20,'multi_review_orders':2,'distinct_orders':100,'average_score':'3.7','low_rating_rate_pct':'25.0','review_coverage_pct':'80.0','invalid_scores':0,'invalid_flags':0}
checks=0
def passes(name,fn):
 global checks
 fn();checks+=1;print('PASS:',name)
def rejected(name,fn):
 def wrapped():
  try:fn()
  except ReviewRejected:return
  raise AssertionError('Expected rejection '+name)
 passes(name,wrapped)
passes('valid rate',lambda:validate_metric(P,{'rows':[R]}))
for m in ['average_review_score','review_coverage','reviewed_order_count']:
 passes('valid '+m,lambda m=m:validate_metric(compile_metric(m,'2018-06-01','2018-07-01'),{'rows':[R]}))
for bad in ['nonmetric','effective_contribution_profit']:
 rejected('unregistered '+bad,lambda bad=bad:compile_metric(bad,'2018-06-01','2018-07-01'))
for a,b in [('2018-02-30','2018-03-01'),('2018-07-01','2018-06-01'),('2018-01-01','2019-07-01'),("2018-01-01';DROP TABLE x",'2018-02-01')]:
 rejected('bad period '+a,lambda a=a,b=b:compile_metric('low_rating_rate',a,b))
for key,value in [('distinct_orders',101),('eligible_orders',0),('reviewed_orders',101),('low_rating_orders',81),('low_rating_rate_pct','24'),('review_coverage_pct','70'),('invalid_scores',1),('invalid_flags',1),('average_score','6'),('multi_review_orders',101)]:
 rejected('invalid '+key,lambda key=key,value=value:validate_metric(P,{'rows':{**R,key:value}}))
rejected('multiple rows',lambda:validate_metric(P,{'rows':[R,R]}))
rejected('tampered SQL',lambda:validate_metric({**P,'sql':P['sql']+' -- injected'}, {'rows':[R]}))
rejected('tampered policy',lambda:validate_metric({**P,'policy':'raw_review_rows'}, {'rows':[R]}))
rejected('missing reviews',lambda:validate_metric(P,{'rows':{**R,'reviewed_orders':0,'low_rating_orders':0,'average_score':None,'low_rating_rate_pct':None,'review_coverage_pct':'0'}}))
async def run():
 async def reader(sql,purpose):
  assert 'semantic.order_review_evidence_v1' in sql and '2018-06-01' in sql and '2018-07-01' in sql
  return R
 return await measure('review_coverage','2018-06-01','2018-07-01',reader)
passes('reader integration',lambda:asyncio.run(run()))
print(f'Checks passed: {checks}/{checks}')
