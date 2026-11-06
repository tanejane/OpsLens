"""Run with python -m scripts.phase4b45_validate_results"""
from agent.phase4b43_graph_planner import AnalysisRequest
from agent.phase4b45_result_validation import assess_result,coverage_probe

REQ=AnalysisRequest('unique_orders',('seller_id',),'2018-07-01','2018-08-01','asc',5)
PLAN={'metric':'unique_orders','dimensions':['seller_id']}
probe=lambda n: {'rows':[{'eligible_source_rows':n}]}
metric=lambda values: {'rows':[{'seller_id':str(i),'metric_value':v} for i,v in enumerate(values)]}


def run():
    checks=[]
    def check(name,condition):
        assert condition,name
        checks.append(name);print('PASS:',name)
    check('coverage missing -> not zero',assess_result(REQ,PLAN,probe(0),metric([])).status=='NO_SOURCE_COVERAGE')
    check('coverage errors fail closed',assess_result(REQ,PLAN,{'ok':False},metric([1])).status=='UNVERIFIED')
    check('source exists but no matching groups',assess_result(REQ,PLAN,probe(40),metric([])).status=='NO_MATCHING_GROUPS')
    check('null metric is undefined',assess_result(REQ,PLAN,probe(40),metric([None])).status=='UNDEFINED_METRIC')
    check('zero metric is valid when measured',assess_result(REQ,PLAN,probe(40),metric([0])).status=='MEASURED_WITH_LIMITATIONS')
    check('malformed metric fails closed',assess_result(REQ,PLAN,probe(40),{'rows':[{'wrong':1}]}).status=='UNVERIFIED')
    check('unexpected scalar row count blocked',assess_result(AnalysisRequest('gross_margin_pct',(),'2018-07-01','2018-08-01'),PLAN,probe(40),metric([1,2])).status=='UNVERIFIED')
    ties=assess_result(REQ,PLAN,probe(40),metric([1,1,1,1,1]))
    check('tie disclosures included',any('tie' in s.lower() for s in ties.observations))
    check('inactive sellers not silently included',any('zero-activity' in s for s in ties.observations))
    check('row limit disclosure included',any('row limit' in s for s in ties.observations))
    class Dummy:
        metrics={'unique_orders':{'source':'commerce.orders'}}
        sources={'commerce.orders':{'date_column':'order_purchase_timestamp'}}
    sql=coverage_probe(PLAN,REQ,Dummy())
    check('source probe is a bounded count', 'COUNT(*) AS eligible_source_rows' in sql and 'LIMIT 1' in sql)
    check('source probe uses explicit month boundaries', "DATE '2018-07-01'" in sql and "DATE '2018-08-01'" in sql)
    print(f'Checks passed: {len(checks)}/{len(checks)}')
if __name__=='__main__':run()
