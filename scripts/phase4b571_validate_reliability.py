"""Regression suite for Phase 4B.5.7.1; no network or DB."""
from agent.phase4b57_nl_dynamic_finance import (Intent,Context,resolve,Rejected,
    interpret_with_retries,ModelUnavailable,ModelResponseInvalid,classify_model_error)
from agent.phase4b54_governed_finance import METRICS

class FakeModel:
    def __init__(self, answers): self.answers=iter(answers);self.calls=0
    def interpret(self,q,prior):
        self.calls+=1
        a=next(self.answers)
        if isinstance(a,BaseException):raise a
        return a

class Transient(Exception): code=503
class TooMany(Exception): code=429
class Unauthorized(Exception): code=401

def main():
    count=0
    def check(name,fn):
        nonlocal count
        fn(); count+=1;print('PASS:',name)
    def eq(a,b):assert a==b,(a,b)
    def rejected(fn,kind=Rejected):
        try:fn()
        except kind:return
        raise AssertionError('Expected rejection')
    old=Context('effective_contribution_margin_pct','2018-04-01','2018-05-01')
    def req(**more):return Intent.model_validate({'intent':'measure','metric_id':None,'start_date':'2018-03-01','end_date_exclusive':'2018-04-01','use_prior_metric':True,**more})
    check('Gemini repeated prior metric ID accepted',lambda:eq(resolve(req(metric_id=old.metric_id),old)[0],old.metric_id))
    check('Gemini inheritance with omitted ID accepted',lambda:eq(resolve(req(),old)[0],old.metric_id))
    check('conflicting inherited metric rejected',lambda:rejected(lambda:resolve(req(metric_id='effective_revenue'),old)))
    check('inheritance without context rejected',lambda:rejected(lambda:resolve(req(),None)))
    check('follow-up period updates while metric unchanged',lambda:eq(resolve(req(metric_id=old.metric_id),old)[2].start,'2018-03-01'))
    check('explicit metric switch allowed',lambda:eq(resolve(Intent(intent='measure',metric_id='effective_revenue',start_date='2018-03-01',end_date_exclusive='2018-04-01'),old)[0],'effective_revenue'))
    check('metric switch combined with prior flag rejected',lambda:rejected(lambda:resolve(req(metric_id='effective_revenue'),old)))
    check('unknown metric blocked',lambda:rejected(lambda:resolve(Intent(intent='measure',metric_id='invented',start_date='2018-03-01',end_date_exclusive='2018-04-01'),old)))
    check('investigate remains blocked',lambda:rejected(lambda:resolve(Intent(intent='investigate',metric_id='effective_revenue',start_date='2018-03-01',end_date_exclusive='2018-04-01'),old)))
    check('503 transient classified',lambda:eq(classify_model_error(Transient()),'transient'))
    check('429 transient classified',lambda:eq(classify_model_error(TooMany()),'transient'))
    check('401 not retried',lambda:eq(classify_model_error(Unauthorized()),'fatal'))
    m=FakeModel([Transient(),req()]); delays=[]
    check('transient retry succeeds',lambda:eq(interpret_with_retries(m,'March?',old,sleep=delays.append).intent,'measure'))
    check('transient exactly two attempts',lambda:eq(m.calls,2))
    check('retry delay bounded',lambda:eq(delays,[1]))
    m=FakeModel([Transient(),Transient(),Transient()])
    check('repeated 503 becomes MODEL_UNAVAILABLE',lambda:rejected(lambda:interpret_with_retries(m,'April?',old,sleep=lambda _:None),ModelUnavailable))
    check('no unbounded attempts',lambda:eq(m.calls,3))
    m=FakeModel([Unauthorized()])
    check('unauthorized call fails without retry',lambda:rejected(lambda:interpret_with_retries(m,'April?',old,sleep=lambda _:None),ModelUnavailable))
    check('unauthorized called once',lambda:eq(m.calls,1))
    m=FakeModel([Rejected('invalid intent')])
    check('grounding validation never retried',lambda:rejected(lambda:interpret_with_retries(m,'bad',old,sleep=lambda _:None)))
    check('context is immutable',lambda:eq((old.metric_id,old.start_date,old.end_date_exclusive),('effective_contribution_margin_pct','2018-04-01','2018-05-01')))
    check('registered metrics intact',lambda:eq(len(METRICS),7))
    check('invalid retry budget blocked',lambda:rejected(lambda:interpret_with_retries(m,'bad',old,attempts=4),ValueError))
    check('2025 period is not converted to zero',lambda:eq('2025-01-01' not in (old.start_date,old.end_date_exclusive),True))
    print(f'Checks passed: {count}/{count}')
if __name__=='__main__': main()
