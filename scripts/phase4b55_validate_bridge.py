"""No DB required; verifies finance dispatch and existing graph unchanged."""
from agent.phase4b55_semantic_bridge import SemanticQuery, compile_query, finance_evidence, finance_comparison
from agent.phase4b54_governed_finance import FinanceGateError

def report():
    checks=['ONE_ROW_PER_ORDER','ITEM_PARTITION','ITEMS_EQUAL_FINANCIAL_POPULATION','STATUS_BREAKDOWN_BALANCES',
      'FINANCE_GRAIN_MATCHES','PERIOD_AND_ITEM_INTEGRITY','COVERAGE','DAILY_REVENUE','DAILY_COGS',
      'DAILY_PROFIT','DAILY_ORDER_POPULATION','VALID_MARGIN_DENOMINATOR']
    def period(a,b):
        return {'period':[a,b],'status':'RECONCILED_FOR_REVIEW','execution_approved':False,
                'checks':[{'name':c,'passed':True} for c in checks],
                'measurements':{'orders_with_items':10,'financial_orders':10}}
    return {'phase':'4B.5.3','status':'REVIEW_ELIGIBLE','execution_approved':False,'periods':[
       period('2017-11-01','2017-12-01'),period('2018-03-01','2018-04-01'),period('2018-06-01','2018-07-01')]}

def main():
    r=report();passed=0
    def check(name,fn):
        nonlocal passed
        fn();passed+=1;print('PASS:',name)
    def reject(fn):
        try:fn()
        except (ValueError,FinanceGateError):return
        raise AssertionError('Unsafe input accepted')
    p=compile_query(SemanticQuery('effective_revenue','2018-06-01','2018-07-01'),reconciliation=r)
    check('finance dispatched',lambda:assert_equal(p['route'],'governed_finance'))
    check('SQL single-source',lambda:assert_true('JOIN' not in p['plan']['sql']))
    check('reconciliation evidence gate',lambda:reject(lambda:compile_query(SemanticQuery('effective_revenue','2018-06-01','2018-07-01'),reconciliation={})))
    check('unverified period blocked',lambda:reject(lambda:compile_query(SemanticQuery('effective_revenue','2018-07-01','2018-08-01'),reconciliation=r)))
    check('dimension blocked',lambda:reject(lambda:compile_query(SemanticQuery('effective_revenue','2018-06-01','2018-07-01',('seller_id',)),reconciliation=r)))
    check('ranking blocked',lambda:reject(lambda:compile_query(SemanticQuery('effective_revenue','2018-06-01','2018-07-01',order='asc'),reconciliation=r)))
    check('nonfinance needs graph planner',lambda:reject(lambda:compile_query(SemanticQuery('unique_orders','2018-06-01','2018-07-01'),reconciliation=r)))
    check('injection rejected',lambda:reject(lambda:compile_query(SemanticQuery('effective_revenue',"2018-06-01';DROP",'2018-07-01'),reconciliation=r)))
    check('graph never silently emulates finance',lambda:assert_equal(p['metric'],'effective_revenue'))
    class FakePlanner:
        def compile(self, req):
            assert req.metric == 'unique_orders' and req.dimensions == ('seller_id',)
            return {'sql': 'SELECT 1 LIMIT 1', 'metric': req.metric, 'dimensions': list(req.dimensions)}
    routed=compile_query(SemanticQuery('unique_orders','2018-06-01','2018-07-01',('seller_id',)),
                         reconciliation=r,graph_planner=FakePlanner())
    check('existing graph planner handoff',lambda:assert_equal(routed['route'],'existing_graph'))
    check('graph dimension carried through',lambda:assert_equal(routed['approved_dimensions'],['seller_id']))

    result=finance_evidence(p,{'rows':[{'eligible_source_rows':6160,'metric_value':'865124.31'}]})
    check('evidence source and population',lambda:assert_equal((result['source'],result['source_population_rows']),('semantic.order_economics',6160)))
    check('causal claim false',lambda:assert_equal(result['causal_claim'],False))
    check('null rejected',lambda:reject(lambda:finance_evidence(p,{'rows':[{'eligible_source_rows':10,'metric_value':None}]})))
    check('no coverage rejected',lambda:reject(lambda:finance_evidence(p,{'rows':[{'eligible_source_rows':0,'metric_value':0}]})))
    q=compile_query(SemanticQuery('effective_revenue','2018-03-01','2018-04-01'),reconciliation=r)
    result2=finance_evidence(q,{'rows':[{'eligible_source_rows':7188,'metric_value':'983213.44'}]})
    cmp=finance_comparison(result,result2)
    check('comparison exact delta',lambda:assert_equal(cmp['absolute_change'],'118089.13'))
    check('comparison no causality',lambda:assert_equal(cmp['causal_claim'],False))
    check('incompatible comparisons rejected',lambda:reject(lambda:finance_comparison(result,{**result2,'metric_id':'another'})))
    print(f'Checks passed: {passed}/{passed}')

def assert_equal(a,b):
    if a!=b:raise AssertionError((a,b))
def assert_true(x):
    if not x:raise AssertionError('Expected true')
if __name__=='__main__':main()
