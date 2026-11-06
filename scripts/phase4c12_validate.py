"""Offline, no network: deterministic grounding and independent-state guarantees."""
import asyncio
from agent.phase4c12_cx_nlp import CXContext, CXSession, candidate, ground, execute_cx
from agent.phase4c11_satisfaction import compile_metric

cases=[
 ('What was our average customer satisfaction score in June 2018?',None,'average_review_score','2018-06-01'),
 ('How happy were our customers in June 2018?',None,'average_review_score','2018-06-01'),
 ('What percentage of orders received bad reviews in June 2018?',None,'low_rating_rate','2018-06-01'),
 ('What was review coverage in June 2018?',None,'review_coverage','2018-06-01'),
 ('How many reviewed orders in June 2018?',None,'reviewed_order_count','2018-06-01'),
 ('What about May 2018?',CXContext('average_review_score','2018-06-01','2018-07-01'),'average_review_score','2018-05-01'),
 ('And the bad review rate?',CXContext('average_review_score','2018-05-01','2018-06-01'),'low_rating_rate','2018-05-01'),
]
count=0
for q,prev,metric,start in cases:
 a,s,_=ground(q,prev)
 assert s is None and a[0]==metric and a[1]==start,(q,a,s)
 print('PASS:',q);count+=1
for q,prev,expected in [
 ('What was our average satisfaction?',None,'NEEDS_CLARIFICATION'),
 ('What about that?',CXContext('average_review_score','2018-06-01','2018-07-01'),'NEEDS_CLARIFICATION'),
 ('Why did satisfaction drop in June 2018?',None,'NOT_YET_SUPPORTED'),
 ('Did satisfaction drop from May to June 2018?',None,'NOT_YET_SUPPORTED'),
 ('How many customers left reviews in June 2018?',None,'NEEDS_CLARIFICATION'),
 ('Give satisfaction for June 2018 and May 2018',None,'NEEDS_CLARIFICATION'),
]:
 _,s,_=ground(q,prev)
 assert s==expected,(q,s,expected)
 print('PASS: blocked',q);count+=1
assert not candidate('Which sellers had most orders in June 2018?',CXContext('average_review_score','2018-06-01','2018-07-01'));count+=1

async def integration():
 calls=[]
 async def forbidden(*a):raise AssertionError('Unexpected delegated route')
 async def fake_reader(sql,purpose):
  calls.append(sql)
  return {'eligible_orders':100,'reviewed_orders':90,'low_rating_orders':9,'multi_review_orders':0,'average_score':'4.2','low_rating_rate_pct':'10','review_coverage_pct':'90','distinct_orders':100,'invalid_scores':0,'invalid_flags':0}
 session=CXSession(object())
 async def prior(*a):
  return {'route':'finance_measure','executable':True},object()
 r=await session.dispatch('Average review score in June 2018',prior,None,None,fake_reader,None,None,None,None)
 assert r['evidence']['value']=='4.2' and len(calls)==1
 r=await session.dispatch('What about May 2018?',prior,None,None,fake_reader,None,None,None,None)
 assert r['evidence']['period'][0]=='2018-05-01' and len(calls)==2
 r=await session.dispatch('And the bad review rate?',prior,None,None,fake_reader,None,None,None,None)
 assert r['evidence']['metric_id']=='low_rating_rate' and len(calls)==3
 r=await session.dispatch('Did satisfaction drop from May to June 2018?',prior,None,None,fake_reader,None,None,None,None)
 assert not r['executable'] and len(calls)==3
 r=await session.dispatch('What was effective revenue in April 2018?',prior,None,None,fake_reader,None,None,None,None)
 assert r['route']=='finance_measure' and session.active_domain=='finance_measure'
 r=await session.dispatch('What about May 2018?',prior,None,None,fake_reader,None,None,None,None)
 assert r['route']=='finance_measure' and len(calls)==3
 return 6
count+=asyncio.run(integration())
print(f'Checks passed: {count}/{count}')
