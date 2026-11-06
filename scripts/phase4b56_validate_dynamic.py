from agent.phase4b56_dynamic_period import requested_period,audit_queries,audit_token,compile_metric,measurement_evidence,DynamicPeriodRejected
from agent.phase4b53_eligibility import assess
from copy import deepcopy

def fixtures():
    return {'cohort':{'placed':10,'placed_distinct':10,'with_items':8,'without_items':2,'represented':8,
        'item_missing_finance':0,'finance_missing_item':0,'canceled_missing':1,'unavailable_missing':0,
        'created_missing':1,'other_missing':0,'null_status_missing':0},
        'finance':{'rows':8,'unique_orders':8,'revenue':100,'cogs':60,'profit':20},
        'daily':{'days':2,'revenue':100,'cogs':60,'profit':20,'orders':8},
        'integrity':{'financial_rows':8,'finance_only':0,'period_mismatch':0,'no_items':0}}

def reject(fn):
    try: fn()
    except (ValueError,TypeError): return
    raise AssertionError('Expected rejection')

def test():
    n=0
    def check(name,fn):
        nonlocal n
        fn();n+=1;print('PASS:',name)
    p=requested_period('2018-04-01','2018-05-01')
    data=fixtures();tok=audit_token(p,data)
    check('unseen interval verified from live shaped rows',lambda:assert_true(tok['status']=='RECONCILED_FOR_REVIEW'))
    check('four audited queries from existing reconciler',lambda:assert_true(set(audit_queries(p))=={'cohort','finance','daily','integrity'}))
    check('registered finance metric compiles',lambda:assert_true('SUM(' in compile_metric('effective_revenue',p,tok)['sql']))
    check('date range half-open',lambda:assert_true("< DATE '2018-05-01'" in compile_metric('effective_revenue',p,tok)['sql']))
    check('finance sources qualified',lambda:assert_true('"semantic"."order_economics"' in compile_metric('effective_revenue',p,tok)['sql']))
    check('metric unknown rejected',lambda:reject(lambda:compile_metric('foo',p,tok)))
    check('join rejected',lambda:reject(lambda:compile_metric('effective_revenue',p,tok,joins=('x',))))
    check('dimension rejected',lambda:reject(lambda:compile_metric('effective_revenue',p,tok,dimensions=('seller_id',))))
    check('period mismatch rejected',lambda:reject(lambda:compile_metric('effective_revenue',requested_period('2018-05-01','2018-06-01'),tok)))
    check('invalid date rejected',lambda:reject(lambda:requested_period('2018-04-01;DROP','2018-05-01')))
    check('backward interval rejected',lambda:reject(lambda:requested_period('2018-05-01','2018-04-01')))
    check('unbounded interval rejected',lambda:reject(lambda:requested_period('2017-01-01','2018-06-01')))
    bad=fixtures();bad['cohort']['item_missing_finance']=1
    check('population mismatch blocks',lambda:reject(lambda:audit_token(p,bad)))
    bad=fixtures();bad['daily']['revenue']=110
    check('aggregate mismatch blocks',lambda:reject(lambda:audit_token(p,bad)))
    bad=fixtures();bad['integrity']['finance_only']=1
    check('integrity mismatch blocks',lambda:reject(lambda:audit_token(p,bad)))
    check('missing auditor query blocks',lambda:reject(lambda:audit_token(p,{'cohort':data['cohort']})))
    plan=compile_metric('effective_revenue',p,tok)
    good={'rows':[{'eligible_source_rows':8,'metric_value':100}]}
    check('structured measured evidence',lambda:assert_true(measurement_evidence(plan,good,tok)['value']=='100'))
    check('causal claim remains false',lambda:assert_true(measurement_evidence(plan,good,tok)['causal_claim'] is False))
    check('no coverage blocked',lambda:reject(lambda:measurement_evidence(plan,{'rows':[{'eligible_source_rows':0,'metric_value':0}]},tok)))
    check('null metric blocked',lambda:reject(lambda:measurement_evidence(plan,{'rows':[{'eligible_source_rows':8,'metric_value':None}]},tok)))
    print(f'Checks passed: {n}/{n}')

def assert_true(b):
    if not b:raise AssertionError('Check failed')

if __name__=='__main__':test()
