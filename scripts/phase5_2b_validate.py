"""Offline audit contract regression tests; no DB needed."""
from copy import deepcopy
from pathlib import Path
from scripts.phase5_2b_assess import assess, CohortAuditRejected, COUNTS, GLOBAL

def fixture():
    month=[]
    for start,end,n in [('2018-05-01','2018-06-01',6873),('2018-06-01','2018-07-01',6167)]:
        month.append(dict(month_start=start,month_end=end,**{k:n if k in COUNTS[:6] else 0 for k in COUNTS}))
    return {'contract':'PHASE5_2B_EXACT_ORDER_COHORT_V1','time_basis':'order_purchase_time',
            'month_pairs':month,'global_quality':{k:0 for k in GLOBAL},
            'read_only':True,'approved_for_mcp':False,'causal_claim':False}

def run():
    tests=[]
    def check(name, change=None, expect='EXACT_ORDER_COHORT_RECONCILIATION_FAILED'):
        p=fixture()
        if change:change(p)
        try:
            out=assess(p)
            assert out['status']==expect,(name,out)
            assert out['approved_for_mcp'] is False and out['causal_claim'] is False
        except CohortAuditRejected:
            assert expect=='EXACT_ORDER_COHORT_RECONCILIATION_FAILED',name
        tests.append(name)
        print('PASS:',name)
    check('matched exact cohorts',expect='EXACT_ORDER_COHORT_RECONCILED')
    for k in COUNTS[6:]:
        check('detect '+k,lambda p,k=k:p['month_pairs'][0].__setitem__(k,1))
    for k in GLOBAL:
        check('global '+k,lambda p,k=k:p['global_quality'].__setitem__(k,1))
    for k in COUNTS[:6]:
        check('bad count '+k,lambda p,k=k:p['month_pairs'][1].__setitem__(k,-1))
    for k in COUNTS[:6]:
        check('unequal count '+k,lambda p,k=k:p['month_pairs'][1].__setitem__(k,6166))
    check('missing period',lambda p:p['month_pairs'].pop())
    check('swapped periods',lambda p:p['month_pairs'].reverse())
    check('fake period',lambda p:p['month_pairs'][0].__setitem__('month_start','2018-04-01'))
    check('unknown field',lambda p:p.__setitem__('authorization','yes'))
    check('extra month field',lambda p:p['month_pairs'][0].__setitem__('unsafe','value'))
    check('wrong contract',lambda p:p.__setitem__('contract','fake'))
    check('MCP approval flag',lambda p:p.__setitem__('approved_for_mcp',True))
    check('causal flag',lambda p:p.__setitem__('causal_claim',True))
    check('read only flag',lambda p:p.__setitem__('read_only',False))
    check('wrong time basis',lambda p:p.__setitem__('time_basis','delivered_at'))
    check('boolean instead of count',lambda p:p['month_pairs'][0].__setitem__('source_rows',True))
    check('missing global field',lambda p:p['global_quality'].pop('review_duplicate_order_ids'))
    check('empty cohort',lambda p:[p['month_pairs'][0].__setitem__(k,0) for k in COUNTS[:6]])
    check('bad data type',lambda p:p.__setitem__('month_pairs','2018-05'))
    check('missing month field',lambda p:p['month_pairs'][0].pop('delivery_rows'))
    sql=Path(__file__).resolve().parents[1]/'sql'/'phase5_2b_order_cohort_audit.sql'
    source=sql.read_text(encoding='utf-8')
    for phrase in ['commerce.orders','semantic.order_delivery_evidence_v1','semantic.order_review_evidence_v1',
                   'EXCEPT','IS DISTINCT FROM','json_build_object','2018-05-01','2018-06-01']:
        assert phrase in source,phrase
        tests.append('SQL includes '+phrase);print('PASS: SQL includes',phrase)
    import re
    assert not re.search(r'\b(?:GRANT|REVOKE|CREATE|DROP|ALTER|INSERT|UPDATE|DELETE|TRUNCATE)\b',re.sub(r'--[^\n]*','',source),re.I)
    tests.append('read-only SQL');print('PASS: read-only SQL')
    print(f'Checks passed: {len(tests)}/{len(tests)}')
if __name__=='__main__':run()
