"""Offline tests for conservative product NLP routing and context."""
import asyncio,sys
from decimal import Decimal
from agent.phase4c20_product_nlp import ground,candidate,ProductContext,ProductNLPSession

cases=[
 ('How many health and beauty products were sold in June 2018?',None,'units_sold','2018-06-01','beleza_saude'),
 ('How many orders contained beleza_saude in June 2018?',None,'category_order_count','2018-06-01','beleza_saude'),
 ('What is the item GMV for health_beauty in June 2018?',None,'item_gmv','2018-06-01','beleza_saude'),
 ('What percentage of item GMV was health and beauty in June 2018?',None,'category_gmv_share','2018-06-01','beleza_saude'),
 ('What was the average item price for health & beauty in June 2018?',None,'average_item_price','2018-06-01','beleza_saude'),
 ('What about May 2018?',ProductContext('units_sold','2018-06-01','2018-07-01','beleza_saude'),'units_sold','2018-05-01','beleza_saude'),
 ('And the item GMV?',ProductContext('units_sold','2018-06-01','2018-07-01','beleza_saude'),'item_gmv','2018-06-01','beleza_saude'),
 ('What about December 2017?',ProductContext('item_gmv','2018-06-01','2018-07-01','beleza_saude'),'item_gmv','2017-12-01','beleza_saude')]
for q,prev,m,s,c in cases:
    p,b=ground(q,prev)
    assert b is None,(q,b)
    assert (p.metric_id,p.start,p.category)==(m,s,c),(q,p)
    print('PASS:',q)
blocked=[
 ('How many products sold?',None,'NEEDS_CLARIFICATION'),
 ('How many health and beauty products sold?',None,'NEEDS_CLARIFICATION'),
 ('What was the item GMV in June 2018?',None,'NEEDS_CLARIFICATION'),
 ('What was item GMV for shoes in June 2018?',None,'NEEDS_CLARIFICATION'),
 ('What were the health and beauty stockouts in June 2018?',None,'NOT_YET_SUPPORTED'),
 ('Why did health and beauty sales decrease in June 2018?',None,'NOT_YET_SUPPORTED'),
 ('Compare health and beauty GMV in May 2018 and June 2018',None,'NOT_YET_SUPPORTED'),
 ('Rank top 10 products June 2018',None,'NOT_YET_SUPPORTED'),
 ('How many customers purchased health and beauty in June 2018?',None,'NEEDS_CLARIFICATION'),
 ('How many items sold in May 2018 and June 2018?',None,'NEEDS_CLARIFICATION'),
]
for q,prev,expected in blocked:
    p,b=ground(q,prev)
    assert p is None and b['status']==expected,(q,p,b)
    print('PASS: blocked',q)
assert not candidate('What is the late delivery rate in June 2018?',False)
assert not candidate('Average review score in June 2018?',False)
assert not candidate('What about May 2018?',False)
assert candidate('What about May 2018?',True)
assert candidate('How many health and beauty products sold in June 2018?',False)

class Prior:
    def __init__(self):self.calls=[]
    async def dispatch(self,q,*a):self.calls.append(q);return {'route':'prior'}

async def integration():
    prior=Prior();sess=ProductNLPSession(prior)
    async def reader(sql,purpose):
        assert 'semantic.order_item_product_evidence_v1' in sql
        assert "category='beleza_saude'" in sql
        return {'total_units':7078,'unique_items':7078,'total_orders':6160,'invalid_items':0,
                'category_units':885,'category_unique_items':885,'category_orders':799,'category_invalid_items':0,
                'total_gmv':'865124.31','category_gmv':'107908.82'}
    args=[None,None,None,reader,None,None,None,None]
    a=await sess.dispatch('How many health and beauty products sold in June 2018?',*args)
    assert a['evidence']['value']=='885' and a['resolution']['canonical_category']=='beleza_saude'
    b=await sess.dispatch('And the item GMV?',*args)
    assert b['evidence']['value']=='107908.82'
    c=await sess.dispatch('What about May 2018?',*args)
    assert c['evidence']['period']==['2018-05-01','2018-06-01']
    d=await sess.dispatch('What is the late delivery rate in June 2018?',*args)
    assert d['route']=='prior' and len(prior.calls)==1
    e=await sess.dispatch('What about May 2018?',*args)
    assert e['route']=='prior' and len(prior.calls)==2
    print('PASS: bounded live-reader simulation and prior domain delegation')
asyncio.run(integration())
print('Checks passed:',len(cases)+len(blocked)+6)
