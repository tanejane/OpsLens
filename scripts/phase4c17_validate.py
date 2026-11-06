import asyncio
from agent.phase4c17_delivery_compare import periods,metric,compare_delivery,DeliveryComparisonSession,DeliveryComparisonRejected
from agent.phase4c16_delivery_nlp import DeliveryContext

n=0
def ok(label,expr):
    global n
    assert expr,label
    n+=1;print('PASS:',label)

async def main():
    p=periods('Did late delivery improve from May 2018 to June 2018?')
    ok('two explicit months',p==[('2018-05-01','2018-06-01'),('2018-06-01','2018-07-01')])
    ok('shared year',periods('Compare May to June 2018')==p)
    for name,q in [('missing baseline','Compare delivery in June 2018'),('backward dates','Compare June and May 2018'),('identical months','Compare June 2018 and June 2018'),('no dates','Compare late delivery')]:
        try:periods(q);good=False
        except DeliveryComparisonRejected:good=True
        ok(name,good)
    prev=DeliveryContext('average_delivery_days','2018-06-01','2018-07-01')
    for label,q,expected in [('late rate','Did late deliveries improve from May to June 2018?','late_delivery_rate'),('duration','Compare average delivery time from May to June 2018','average_delivery_days'),('count','Compare delivered order count from May to June 2018','delivered_order_count'),('coverage','Compare delivery evidence coverage from May to June 2018','delivery_evidence_coverage'),('context','Compare May and June 2018','average_delivery_days')]:
        ok(label,metric(q,prev)==expected)
    counts={'2018-05-01':(6873,6749,556,124,'11.41902893535667835577'), '2018-06-01':(6167,6096,85,71,'9.32189345852167784527')}
    calls=[]
    async def reader(sql,purpose):
        period='2018-05-01' if "DATE '2018-05-01'" in sql else '2018-06-01'
        calls.append((period,sql))
        total,eligible,late,missing,avg=counts[period]
        return {'eligible_orders':total,'distinct_orders':total,'lateness_eligible_orders':eligible,'late_orders':late,'duration_eligible_orders':eligible,'missing_actual':missing,'missing_estimated':0,'missing_purchase':0,'invalid_duration':0,'invalid_late_flags':0,'mean_delivery_days':avg,'late_rate_pct':str(100*late/eligible),'lateness_coverage_pct':str(100*eligible/total)}
    out,updated=await compare_delivery('Did late deliveries improve from May to June 2018?',None,reader)
    ok('comparison executable',out['status']=='COMPARISON_MEASURED_WITH_SCOPE_LIMITS')
    ok('late rate decreases',out['direction']=='DECREASED' and out['delta_unit']=='percentage_points')
    ok('two registered queries',len(calls)==2 and 'semantic.order_delivery_evidence_v1' in calls[0][1])
    ok('after context',updated.start=='2018-06-01')
    out,_=await compare_delivery('Compare average delivery time from May to June 2018',None,reader)
    ok('duration declines',out['direction']=='DECREASED' and out['delta_unit']=='days')
    out,_=await compare_delivery('Compare delivery evidence coverage from May to June 2018',None,reader)
    ok('coverage compared',out['metric_id']=='delivery_evidence_coverage')
    out,_=await compare_delivery('Compare delivered order count from May to June 2018',None,reader)
    ok('counts compared',out['metric_id']=='delivered_order_count')
    prior=len(calls)
    out,_=await compare_delivery('Compare delivery from June to May 2018',None,reader)
    ok('reject backward no SQL',out['status']=='NEEDS_CLARIFICATION' and len(calls)==prior)
    s=DeliveryComparisonSession(object())
    async def delegate(q,state,*args):return {'route':'finance_measure','executable':True,'marker':'delegated'},state
    args=(delegate,None,None,reader,None,None,None,None)
    out=await s.dispatch('Did late delivery improve from May 2018 to June 2018?',*args)
    ok('unified compare',out['executable'] and s.active_domain=='delivery_operations')
    out=await s.dispatch('What about May 2018?',*args)
    ok('single month followup',out['evidence']['metric_id']=='late_delivery_rate' and out['evidence']['period'][0]=='2018-05-01')
    out=await s.dispatch('What was our effective revenue in April 2018?',*args)
    ok('finance delegation',out['marker']=='delegated' and s.active_domain=='finance_measure')
    before=len(calls)
    out=await s.dispatch('What about May 2018?',*args)
    ok('context isolation',out['marker']=='delegated' and len(calls)==before)
    ok('no causal claim',not out.get('causal_claim',False))
    print(f'Checks passed: {n}/{n}')
if __name__=='__main__':asyncio.run(main())
