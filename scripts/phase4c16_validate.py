import asyncio
from agent.phase4c16_delivery_nlp import ground_delivery,delivery_candidate,DeliveryNLPSession,DeliveryContext
from agent.phase4c15_delivery import compile_metric

checks=0
def check(name,condition):
    global checks
    assert condition,name
    checks+=1;print('PASS:',name)

def test_ground():
    samples=[
        ('What percentage of orders were delivered late in June 2018?','late_delivery_rate','2018-06-01'),
        ('How long did deliveries take in May 2018?','average_delivery_days','2018-05-01'),
        ('How many orders were delivered in June 2018?','delivered_order_count','2018-06-01'),
        ('What was delivery evidence coverage in June 2018?','delivery_evidence_coverage','2018-06-01')]
    for q,m,start in samples:
        args,blocked=ground_delivery(q,None)
        check(m,not blocked and args[0]==m and args[1]==start)
    prev=DeliveryContext('average_delivery_days','2018-05-01','2018-06-01')
    args,_=ground_delivery('What about June 2018?',prev)
    check('period followup',args==('average_delivery_days','2018-06-01','2018-07-01'))
    args,_=ground_delivery('And the late delivery rate?',prev)
    check('metric followup',args==('late_delivery_rate','2018-05-01','2018-06-01'))
    for q,expected in [
        ('Why were deliveries late in June 2018?','NOT_YET_SUPPORTED'),
        ('Did late delivery improve from May 2018 to June 2018?','NOT_YET_SUPPORTED'),
        ('What percentage of orders were delivered late?','NEEDS_CLARIFICATION'),
        ('How many customers received deliveries in June 2018?','NEEDS_CLARIFICATION'),
        ('How long did delivery take in May 2018 versus June 2018?','NOT_YET_SUPPORTED')]:
        args,result=ground_delivery(q,None)
        check(q,args is None and result['status']==expected)
    check('not misroute satisfaction',not delivery_candidate('What was our review score in June 2018?',False))
    check('not misroute finance',not delivery_candidate('What was effective revenue in June 2018?',False))
    check('approved SQL only', 'semantic.order_delivery_evidence_v1' in compile_metric('late_delivery_rate','2018-06-01','2018-07-01')['sql'])

async def test_session():
    s=DeliveryNLPSession(object())
    queries=[]
    async def reader(sql,purpose):
        queries.append(sql)
        return {'eligible_orders':6167,'distinct_orders':6167,'lateness_eligible_orders':6096,'late_orders':85,'duration_eligible_orders':6096,'missing_actual':71,'missing_estimated':0,'missing_purchase':0,'invalid_duration':0,'invalid_late_flags':0,'mean_delivery_days':'9.32189345852167784527','late_rate_pct':str(100*85/6096),'lateness_coverage_pct':str(100*6096/6167)}
    async def prior(q,state,*args):
        return {'route':'finance_measure','executable':True,'marker':'delegated'},state
    args=(prior,None,None,reader,None,None,None,None)
    out=await s.dispatch('What percentage of orders were delivered late in June 2018?',*args)
    check('live adapter',out['route']=='delivery_operations' and out['executable'] and out['evidence']['metric_id']=='late_delivery_rate')
    check('one governed SQL',len(queries)==1)
    out=await s.dispatch('What about May 2018?',*args)
    check('session inherited metric',out['evidence']['metric_id']=='late_delivery_rate' and out['evidence']['period'][0]=='2018-05-01')
    out=await s.dispatch('How long did deliveries take in June 2018?',*args)
    check('switch metric',out['evidence']['metric_id']=='average_delivery_days')
    out=await s.dispatch('What was our effective revenue in April 2018?',*args)
    check('finance delegating',out['marker']=='delegated' and s.active_domain=='finance_measure')
    count=len(queries)
    out=await s.dispatch('What about May 2018?',*args)
    check('domain followup not delivery',out['marker']=='delegated' and len(queries)==count)
    before=s.delivery_context
    out=await s.dispatch('Why were orders delivered late in June 2018?',*args)
    check('unsupported blocked',out['status']=='NOT_YET_SUPPORTED' and s.delivery_context==before)
    check('no sql on block',len(queries)==count)

if __name__=='__main__':
    test_ground();asyncio.run(test_session());print(f'Checks passed: {checks}/{checks}')
