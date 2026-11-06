from agent.phase4b51_metric_contracts import CHECKS,query,assess,proposed_catalog,ContractError

def run():
    n=0
    def ok(name,condition):
        nonlocal n
        assert condition,name; n+=1; print('PASS:',name)
    base={'metrics':[{'metric_name':'orders','source_view':'bad'}, {'metric_name':'contribution_margin','source_view':'bad'}]}
    repaired=proposed_catalog(base)
    ok('orders source corrected',repaired['metrics'][0]['source_view']=='commerce.orders')
    ok('contribution margin source corrected',repaired['metrics'][1]['source_view']=='semantic.order_economics')
    ok('source catalog not mutated',base['metrics'][0]['source_view']=='bad')
    ok('catalog remains unapproved',repaired['approval_status']=='NOT_EXECUTION_APPROVED')
    sql=query('orders','2018-06-01','2018-07-01')
    ok('distinct order metric', 'COUNT(DISTINCT "order_id")' in sql)
    ok('date range half-open',"DATE '2018-06-01'" in sql and "DATE '2018-07-01'" in sql and '< DATE' in sql)
    ok('ratio uses sums', 'SUM("effective_contribution_profit") / NULLIF(SUM("effective_revenue"),0)' in query('effective_contribution_margin_pct','2018-06-01','2018-07-01'))
    for name,fn in [('unknown metric refused',lambda:query('pretend','2018-06-01','2018-07-01')),
                    ('bad date refused',lambda:query('orders','2018-07-01','2018-06-01')),
                    ('injection date refused',lambda:query('orders',"2018-06-01'; DROP TABLE x;--",'2018-07-01'))]:
        try:fn();raise AssertionError('Accepted invalid request')
        except ContractError:ok(name,True)
    audit={'sources':{'commerce.orders':{'live_columns':['order_id','order_purchase_timestamp'],'checks':{'grain':{'status':'VERIFIED'}}}}}
    ok('coverage zero blocks', 'NO_PERIOD_COVERAGE' in assess('orders',{'eligible_source_rows':0,'metric_value':0},audit=audit)['issues'])
    ok('nonzero results require review',assess('orders',{'eligible_source_rows':8,'metric_value':8},audit=audit)['assessment']=='REVIEW_REQUIRED')
    ok('missing metadata blocks','SOURCE_GRAIN_UNVERIFIED' in assess('orders',{'eligible_source_rows':8,'metric_value':8},audit={})['issues'])
    print(f'Checks passed: {n}/{n}')
if __name__=='__main__':run()
