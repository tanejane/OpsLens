"""Offline safety and control-flow checks; does not call Gemini or PostgreSQL."""
from agent.phase4b57_nl_dynamic_finance import Intent,Context,resolve,Rejected,API_SCHEMA
from agent.phase4b54_governed_finance import METRICS

def test():
    count=0
    def ok(name,fun):
        nonlocal count
        fun();count+=1;print('PASS:',name)
    def expect_reject(intent,prior=None):
        try:resolve(intent,prior)
        except (Rejected,ValueError):return
        raise AssertionError('Expected refusal')
    p=Context('effective_contribution_margin_pct','2018-03-01','2018-04-01')
    m=lambda **kw:Intent.model_validate({'intent':'measure','metric_id':'effective_revenue','start_date':'2018-04-01','end_date_exclusive':'2018-05-01',**kw})
    ok('registered finance metric',lambda:assert_eq(resolve(m(),None)[0],'effective_revenue'))
    ok('seven finance contracts',lambda:assert_eq(len(METRICS),7))
    ok('previous metric inherited',lambda:assert_eq(resolve(Intent(intent='measure',use_prior_metric=True,start_date='2018-04-01',end_date_exclusive='2018-05-01'),p)[0],p.metric_id))
    ok('comparison previous period',lambda:assert_eq(resolve(Intent(intent='compare',use_prior_metric=True,use_prior_period_as_comparison=True,start_date='2018-04-01',end_date_exclusive='2018-05-01'),p)[1].start,p.start_date))
    ok('standalone comparison',lambda:assert_eq(resolve(Intent(intent='compare',metric_id='effective_revenue',start_date='2018-04-01',end_date_exclusive='2018-05-01',comparison_start_date='2018-03-01',comparison_end_date_exclusive='2018-04-01'),None)[1].start,'2018-03-01'))
    ok('unknown metric denied',lambda:expect_reject(m(metric_id='mystery')))
    ok('prior absent denied',lambda:expect_reject(Intent(intent='measure',use_prior_metric=True,start_date='2018-04-01',end_date_exclusive='2018-05-01')))
    ok('metric inheritance conflict denied',lambda:expect_reject(m(use_prior_metric=True),p))
    ok('no date denied',lambda:expect_reject(Intent(intent='measure',metric_id='effective_revenue')))
    ok('partial date denied',lambda:expect_reject(Intent(intent='measure',metric_id='effective_revenue',start_date='2018-04-01')))
    ok('backward date denied',lambda:expect_reject(m(end_date_exclusive='2018-03-01')))
    ok('out-of-range year denied',lambda:expect_reject(m(start_date='2025-01-01',end_date_exclusive='2024-02-01')))
    ok('too-long period denied',lambda:expect_reject(m(start_date='2017-01-01',end_date_exclusive='2018-05-01')))
    ok('date injection denied',lambda:expect_reject(m(start_date="2018-04-01';DROP TABLE x;--")))
    ok('comparison missing baseline denied',lambda:expect_reject(m(intent='compare')))
    ok('comparison inheritance without prior denied',lambda:expect_reject(Intent(intent='compare',metric_id='effective_revenue',use_prior_period_as_comparison=True,start_date='2018-04-01',end_date_exclusive='2018-05-01')))
    ok('comparison explicit and inherited conflict denied',lambda:expect_reject(Intent(intent='compare',use_prior_metric=True,use_prior_period_as_comparison=True,comparison_start_date='2018-01-01',comparison_end_date_exclusive='2018-02-01',start_date='2018-04-01',end_date_exclusive='2018-05-01'),p))
    ok('same comparison period denied',lambda:expect_reject(Intent(intent='compare',metric_id='effective_revenue',comparison_start_date='2018-04-01',comparison_end_date_exclusive='2018-05-01',start_date='2018-04-01',end_date_exclusive='2018-05-01')))
    ok('overlapping comparison denied',lambda:expect_reject(Intent(intent='compare',metric_id='effective_revenue',comparison_start_date='2018-03-01',comparison_end_date_exclusive='2018-04-15',start_date='2018-04-01',end_date_exclusive='2018-05-01')))
    ok('why is not a measurement',lambda:expect_reject(Intent(intent='investigate',metric_id='effective_revenue',start_date='2018-03-01',end_date_exclusive='2018-04-01')))
    ok('clarification is not a measurement',lambda:expect_reject(Intent(intent='clarify',ambiguity='which region?')))
    ok('extra SQL field refused',lambda:expect_invalid({'intent':'measure','sql':'drop table x'}))
    ok('Gemini API catalog no SQL field',lambda:assert_eq('sql' in API_SCHEMA['properties'],False))
    print(f'Checks passed: {count}/{count}')
def assert_eq(a,b):assert a==b,(a,b)
def expect_invalid(d):
    try:Intent.model_validate(d)
    except ValueError:return
    raise AssertionError('Expected validation error')
if __name__=='__main__':test()
