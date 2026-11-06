"""Offline deterministic contract/negative tests for governed delivery metrics."""
import asyncio,copy
from agent.phase4c15_delivery import METRICS,compile_metric,validate_metric,measure,DeliveryRejected
from scripts.phase4c15_compare import compare
BASE={'eligible_orders':100,'distinct_orders':100,'lateness_eligible_orders':90,'late_orders':9,'duration_eligible_orders':90,'missing_actual':10,'missing_estimated':0,'missing_purchase':0,'invalid_duration':0,'invalid_late_flags':0,'mean_delivery_days':'12.5','late_rate_pct':'10','lateness_coverage_pct':'90'}
P=compile_metric('late_delivery_rate','2018-06-01','2018-07-01')
def must_fail(fn):
    try:fn()
    except (DeliveryRejected,ValueError,KeyError,TypeError):return
    raise AssertionError('Expected rejection')
checks=[]
def test(name,fn):
    fn();checks.append(name);print('PASS:',name)
def result(k='late_delivery_rate',row=None):return validate_metric(compile_metric(k,'2018-06-01','2018-07-01'),{'rows':[BASE if row is None else row]})
def change(k,v):r=BASE.copy();r[k]=v;return r
for k in METRICS:test('valid '+k,lambda k=k:result(k))
for bad in ['2018-02-30','2018-06-01\';DROP','June 2018',None,True]:test('invalid start '+str(bad),lambda bad=bad:must_fail(lambda:compile_metric('late_delivery_rate',bad,'2018-07-01')))
test('inverted dates',lambda:must_fail(lambda:compile_metric('late_delivery_rate','2018-07-01','2018-06-01')))
test('unregistered metric',lambda:must_fail(lambda:compile_metric('seller_count','2018-06-01','2018-07-01')))
test('altered sql',lambda:must_fail(lambda:validate_metric({**P,'sql':'SELECT 1'},{'rows':[BASE]})))
test('altered policy',lambda:must_fail(lambda:validate_metric({**P,'policy':'arbitrary'},{'rows':[BASE]})))
test('duplicate grain',lambda:must_fail(lambda:result(row=change('distinct_orders',99))))
test('invalid late denominator',lambda:must_fail(lambda:result(row=change('late_orders',91))))
test('invalid rate',lambda:must_fail(lambda:result(row=change('late_rate_pct','20'))))
test('invalid coverage',lambda:must_fail(lambda:result(row=change('lateness_coverage_pct','80'))))
test('negative average',lambda:must_fail(lambda:result('average_delivery_days',change('mean_delivery_days','-3'))))
test('invalid late flags',lambda:must_fail(lambda:result(row=change('invalid_late_flags',1))))
test('boolean count',lambda:must_fail(lambda:result(row=change('eligible_orders',True))))
test('missing population mismatch',lambda:must_fail(lambda:result(row=change('missing_actual',99))))
test('zero coverage',lambda:must_fail(lambda:result(row=change('eligible_orders',0))))
test('two rows',lambda:must_fail(lambda:validate_metric(P,{'rows':[BASE,BASE]})))
async def call():
    async def reader(sql,purpose):
        assert sql==P['sql'];return BASE
    return await measure('late_delivery_rate','2018-06-01','2018-07-01',reader)
test('reader integration',lambda:asyncio.run(call()))
M={'status':'LIVE_MCP_VALIDATED','period':['2018-06-01','2018-07-01'],'causal_claim':False,'population':{k:BASE[k] for k in ('eligible_orders','lateness_eligible_orders','late_orders','duration_eligible_orders','missing_actual','missing_estimated','missing_purchase')},'metrics':{k:{'value':str(v)} for k,v in {'late_delivery_rate':10,'average_delivery_days':12.5,'delivered_order_count':90,'delivery_evidence_coverage':90}.items()}}
G={'period':M['period'],'population':M['population'],'metrics':{k:v['value'] for k,v in M['metrics'].items()}}
test('independent comparison',lambda:compare(M,G))
test('reconciliation rejects mismatch',lambda:must_fail(lambda:compare(M,{**G,'metrics':{**G['metrics'],'late_delivery_rate':'11'}})))
print(f'Checks passed: {len(checks)}/{len(checks)}')
