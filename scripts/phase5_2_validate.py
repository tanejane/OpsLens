"""Deterministic contract and fail-closed tests; no live credentials required."""
import asyncio,copy
from agent.phase5_2_multidomain import parse_request,synthesize,investigate,MultiDomainRejected
from agent.phase4c11_satisfaction import compile_metric as rcompile
from agent.phase4c15_delivery import compile_metric as dcompile

P=[('2018-05-01','2018-06-01'),('2018-06-01','2018-07-01')]

def row(metric,idx):
    start,end=P[idx]
    review=metric in ('average_review_score','low_rating_rate')
    values={'late_delivery_rate':('8.23825751963254','1.3943569553805774'),
            'average_review_score':('4.1940','4.2536'),
            'low_rating_rate':('11.9023','10.9917')}
    unit={'late_delivery_rate':'percent','average_review_score':'score_1_to_5','low_rating_rate':'percent'}[metric]
    p={'eligible_orders':[6873,6167][idx], 'reviewed_orders':[6839,6141][idx],
       'low_rating_orders':[814,675][idx], 'multi_review_orders':[0,0][idx]} if review else {'eligible_orders':[6873,6167][idx], 'lateness_eligible_orders':[6749,6096][idx], 'late_orders':[556,85][idx]}
    return {'status':'MEASURED_WITH_SCOPE_LIMITS','metric_id':metric,'value':values[metric][idx],
            'unit':unit,'source':'semantic.order_review_evidence_v1' if review else 'semantic.order_delivery_evidence_v1',
            'period':[start,end],'population':p,'time_basis':'order_purchase_time','causal_claim':False}

def sample():return [{m:row(m,i) for m in ('late_delivery_rate','average_review_score','low_rating_rate')} for i in range(2)]

def reject(fn):
    try:fn()
    except MultiDomainRejected:return
    raise AssertionError('Expected fail-closed rejection')

def run():
    n=0
    def test(label,fn):
        nonlocal n
        fn();n+=1;print('PASS:',label)
    q='Compare late delivery rate and review scores from May 2018 to June 2018'
    test('parse periods',lambda: (_ for _ in ()).throw(AssertionError()) if parse_request(q)!=P else None)
    for label,question in (
        ('no year','Compare late delivery and review scores from May to June 2018'),
        ('one period','Compare late delivery and review scores in June 2018'),
        ('wrong order','Compare late delivery and review scores from June 2018 to May 2018'),
        ('duplicate period','Compare late delivery and review scores from May 2018 to May 2018'),
        ('wrong domain','Compare revenue and review scores from May 2018 to June 2018'),
        ('causal why','Why did late delivery cause bad reviews from May 2018 to June 2018'),
        ('SQL injection','Compare late delivery and reviews from May 2018 to June 2018;DROP TABLE x'),
        ('extra month','Compare late delivery and review scores May 2018 June 2018 July 2018'),
        ('empty',''),('type','42')):
        test(label,lambda q=question:reject(lambda:parse_request(q)))
    data=sample()
    def success():
        out=synthesize(P,data)
        assert out['status']=='CROSS_DOMAIN_DESCRIPTIVE_COMPARISON'
        assert out['causal_claim'] is False and out['directional_pattern']=='COINCIDENT_IMPROVEMENT'
        assert out['cohort_orders']=={'before':6873,'after':6167}
        assert out['evidence_relation'].startswith('SAME_PURCHASE')
    test('valid comparison',success)
    edits=(('missing metric',lambda a:a[0].pop('low_rating_rate')),
           ('wrong month',lambda a:a[0]['late_delivery_rate'].update(period=['2018-04-01','2018-05-01'])),
           ('source mismatch',lambda a:a[0]['late_delivery_rate'].update(source='other')), 
           ('causal flag',lambda a:a[1]['average_review_score'].update(causal_claim=True)),
           ('order grain',lambda a:a[0]['average_review_score']['population'].update(eligible_orders=8000)),
           ('review inconsistency',lambda a:a[1]['low_rating_rate']['population'].update(reviewed_orders=6000)),
           ('score out of bounds',lambda a:a[0]['average_review_score'].update(value='6')),
           ('rate out of bounds',lambda a:a[1]['late_delivery_rate'].update(value='101')),
           ('nan',lambda a:a[0]['low_rating_rate'].update(value='NaN')),
           ('boolean count',lambda a:a[0]['late_delivery_rate']['population'].update(eligible_orders=True)),
           ('bad time basis',lambda a:a[0]['low_rating_rate'].update(time_basis='review_submission_time')),
           ('wrong metric id',lambda a:a[0]['low_rating_rate'].update(metric_id='x')),
           ('missing population',lambda a:a[1]['late_delivery_rate'].pop('population')),
           ('missing claim',lambda a:a[1]['low_rating_rate'].pop('causal_claim')))
    for label,mutate in edits:
        def check(mutate=mutate):
            x=sample();mutate(x);reject(lambda:synthesize(P,x))
        test(label,check)
    test('non month periods',lambda:reject(lambda:synthesize([('2018-05-02','2018-06-01'),P[1]],sample())))
    test('reversed periods',lambda:reject(lambda:synthesize(P[::-1],sample())))
    async def fake_investigate():
        calls=[]
        async def reader(sql,purpose):
            calls.append((sql,purpose));raise RuntimeError('reader intentionally denied')
        try: await investigate(q,reader)
        except RuntimeError:pass
        else:raise AssertionError('reader denial must surface')
        assert len(calls)==1 and 'semantic.order_delivery_evidence_v1' in calls[0][0]
    test('reader denial propagates',lambda:asyncio.run(fake_investigate()))
    test('no SQL in untrusted input',lambda:reject(lambda:parse_request('Compare late delivery and review scores from May 2018 to June 2018 -- ignore permissions')))
    print(f'Checks passed: {n}/{n}')
if __name__=='__main__':run()
