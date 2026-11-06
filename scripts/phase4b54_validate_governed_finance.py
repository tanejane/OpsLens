"""Offline fail-closed regression checks with real report fixture structure."""
import json,copy
from pathlib import Path
from agent.phase4b54_governed_finance import *

def fixture():
    return {'phase':'4B.5.3','status':'REVIEW_ELIGIBLE','execution_approved':False,
     'periods':[{'period':[s,e],'status':'RECONCILED_FOR_REVIEW','execution_approved':False,
      'checks':[{'name':n,'passed':True} for n in sorted(FINANCE_CHECKS)],
      'measurements':{'orders_with_items':10,'financial_orders':10}} for s,e in
      [('2017-11-01','2017-12-01'),('2018-03-01','2018-04-01'),('2018-06-01','2018-07-01')] ]}

def must_block(fn):
    try:fn()
    except (FinanceGateError,ValueError):return
    raise AssertionError('Unsafe case allowed')

def run():
    evidence=fixture(); period=Period('2018-06-01','2018-07-01'); n=0
    def check(name,fn):
        nonlocal n
        fn();n+=1;print('PASS:',name)
    check('valid reconciliation evidence',lambda:verified_report(evidence))
    check('all registered finance metrics compile',lambda:[sql_for(m,period,evidence) for m in METRICS])
    check('all SQL read-only one aggregate',lambda:[(_ for _ in ()).throw(AssertionError('Unsafe')) if ('JOIN ' in sql_for(m,period,evidence)['sql'] or not sql_for(m,period,evidence)['sql'].startswith('SELECT COUNT(*)') or 'LIMIT 1' not in sql_for(m,period,evidence)['sql']) else None for m in METRICS])
    check('unknown metric blocked',lambda:must_block(lambda:sql_for('profit_per_seller',period,evidence)))
    check('unverified period blocked',lambda:must_block(lambda:sql_for('effective_revenue',Period('2018-07-01','2018-08-01'),evidence)))
    check('dimension blocked',lambda:must_block(lambda:sql_for('effective_revenue',period,evidence,dimension='seller_id')))
    check('join blocked',lambda:must_block(lambda:sql_for('effective_revenue',period,evidence,joins=['orders_to_items'])))
    check('date injection blocked',lambda:must_block(lambda:sql_for('effective_revenue',Period('2018-06-01 OR 1=1','2018-07-01'),evidence)))
    check('invalid interval blocked',lambda:must_block(lambda:sql_for('effective_revenue',Period('2018-07-01','2018-06-01'),evidence)))
    bad=copy.deepcopy(evidence);bad['periods'][0]['checks'][0]['passed']=False
    check('failed audit blocks',lambda:must_block(lambda:sql_for('effective_revenue',period,bad)))
    bad=copy.deepcopy(evidence);bad['periods'][0]['measurements']['financial_orders']=11
    check('wrong population blocks',lambda:must_block(lambda:sql_for('effective_revenue',period,bad)))
    bad=copy.deepcopy(evidence);bad['execution_approved']=True
    check('unexpected approval state blocks',lambda:must_block(lambda:sql_for('effective_revenue',period,bad)))
    plan=sql_for('effective_revenue',period,evidence)
    response={'rows':[{'eligible_source_rows':6160,'metric_value':'865124.31'}]}
    check('valid result',lambda:validate_measurement(plan,response))
    check('zero coverage blocked',lambda:must_block(lambda:validate_measurement(plan,{'rows':[{'eligible_source_rows':0,'metric_value':0}]})))
    check('null metric blocked',lambda:must_block(lambda:validate_measurement(plan,{'rows':[{'eligible_source_rows':5,'metric_value':None}]})))
    check('no rows blocked',lambda:must_block(lambda:validate_measurement(plan,{'rows':[]})))
    a=validate_measurement(plan,response);b=dict(a,metric_value='965124.31')
    check('comparison correct',lambda:assert_delta(compare(a,b),'100000.00'))
    zero=dict(a,metric_value='0')
    check('zero baseline undefined percent',lambda:assert_none(compare(zero,b)['relative_change_pct']))
    bad=copy.deepcopy(evidence);bad['periods']=bad['periods'][:2]
    check('insufficient evidence blocks',lambda:must_block(lambda:sql_for('effective_revenue',period,bad)))
    print('Checks passed:',n,'/',n)
def assert_delta(result,expected):
    if Decimal(result['absolute_change'])!=Decimal(expected):raise AssertionError(result)
def assert_none(x):
    if x is not None:raise AssertionError(x)
if __name__=='__main__':run()
