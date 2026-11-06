"""Offline audit attachment, negative fixtures, and no-authority regressions."""
from copy import deepcopy
from pathlib import Path
from agent.phase5_2f_cohort_evidence import apply_cohort_evidence, CohortEvidenceRejected
from scripts.phase5_2d_assess import COUNTS, GLOBAL

def fixture():
    months=[]
    for start,end,n in [('2018-02-01','2018-03-01',6728),('2018-03-01','2018-04-01',7211)]:
        p={'month_start':start,'month_end':end}
        p.update({key:(n if key in ('source_rows','source_unique_orders','delivery_rows','delivery_unique_orders','review_rows','review_unique_orders') else 0) for key in COUNTS})
        months.append(p)
    return {'contract':'PHASE5_2D_EXACT_ORDER_COHORT_V1','time_basis':'order_purchase_time','month_pairs':months,'global_quality':{key:0 for key in GLOBAL},'read_only':True,'approved_for_mcp':False,'causal_claim':False}

from scripts.phase5_2c_validate import fixtures, QUESTION
from agent.phase5_2c_three_domain import combine

tests=0
def check(label,condition):
    global tests
    assert condition,label
    tests+=1;print('PASS:',label)
def rejected(label, raw,report=None):
    try:apply_cohort_evidence(report or base,raw)
    except CohortEvidenceRejected:check(label,True)
    else:check(label,False)

f,o=fixtures()
o['cohort_orders']={'before':6728,'after':7211}
base=combine(QUESTION,f,o)
raw=fixture()
unchanged=deepcopy(base)
plain=apply_cohort_evidence(base,None)
check('without audit no strong cohort claim',plain['operational_cohort_evidence']['exact_order_id_sets_verified'] is False)
check('without audit generic limitation',any('not been attached' in x for x in plain['limitations']))
check('without audit no approval',plain['approved_for_mcp'] is False and plain['causal_claim'] is False)
good=apply_cohort_evidence(base,raw)
check('verified raw artifact upgrades cohort evidence',good['operational_cohort_evidence']['status']=='EXACT_ORDER_COHORT_RECONCILED')
check('verified exact id membership',good['operational_cohort_evidence']['exact_order_id_sets_verified'] is True)
check('verified report removes stale audit limitation',not any('not been attached' in x for x in good['limitations']))
check('verified removes requested audit next-step',not any('exact' in x.lower() and 'order' in x.lower() for x in good['next_validations']))
check('verified preserves finance population separation',good['evidence_relation']=='PERIOD_ALIGNED_SEPARATE_FINANCIAL_AND_OPERATIONAL_POPULATIONS')
check('verified adds trace',good['tool_trace'][-1]['executed_new_sql'] is False)
check('verified does not grant MCP',good['approved_for_mcp'] is False and good['operational_cohort_evidence']['approved_for_mcp'] is False)
check('verified does not claim causation',good['causal_claim'] is False and good['operational_cohort_evidence']['causal_claim'] is False)
check('verified preserves metrics',good['operational_changes']==base['operational_changes'] and good['financial_premise']==base['financial_premise'])
check('input report not mutated',base==unchanged)
check('unrelated limitations intact',len(good['limitations'])>=3)
for field,value in [('approved_for_mcp',True),('causal_claim',True),('read_only',False),('time_basis','delivery_time'),('contract','FAKE')]:
    x=deepcopy(raw);x[field]=value;rejected('reject altered '+field,x)
for field,value in [('source_rows',0),('delivery_unique_orders',6666),('review_unique_orders',6000),('missing_delivery_orders',1),('review_only_orders',1)]:
    x=deepcopy(raw);x['month_pairs'][0][field]=value;rejected('reject tampered '+field,x)
x=deepcopy(raw);x['global_quality']['review_duplicate_order_ids']=1;rejected('reject global duplicate ids',x)
x=deepcopy(raw);x['month_pairs'].reverse();rejected('reject reversed audit periods',x)
x=deepcopy(raw);x['month_pairs'][0]['month_start']='2018-05-01';rejected('reject wrong month',x)
x=deepcopy(raw);x['month_pairs'][0]['source_unique_orders']=6500;rejected('reject altered order counts',x)
x=deepcopy(raw);x['month_pairs'][0]['source_rows']=True;rejected('reject boolean order count',x)
x=deepcopy(raw);x['month_pairs'][1]['extra_review_orders']=1;rejected('reject differing sets',x)
x=deepcopy(raw);x['unexpected']='success';rejected('reject forged extra field',x)
x=deepcopy(base);x['cohort_orders']['before']=8000;rejected('reject report/audit count mismatch',raw,x)
x=deepcopy(base);x['periods']['before']=['2018-05-01','2018-06-01'];rejected('reject report/audit period mismatch',raw,x)
x=deepcopy(base);x['causal_claim']=True;rejected('reject causal report',raw,x)
x=deepcopy(base);x['approved_for_mcp']=True;rejected('reject privileged report',raw,x)
rejected('reject fake success badge',{'status':'EXACT_ORDER_COHORT_RECONCILED'})
rejected('reject null evidence',None if False else {'x':1})
cli=Path(__file__).resolve().parents[1]/'scripts'/'phase5_1_playground.py'
s=cli.read_text(encoding='utf-8')
check('CLI optional explicit audit', "'--cohort-audit'" in s)
check('CLI actually routes audit', 'cohort_audit=cohort_audit' in s)
check('CLI loads raw artifact', 'load_audit(flags.cohort_audit)' in s)
source=(Path(__file__).resolve().parents[1]/'agent'/'phase5_2e_multidomain_router.py').read_text()
check('router uses audit evidence', 'apply_cohort_evidence(report,cohort_audit)' in source)
check('router fails closed on invalid audit', "'COHORT_AUDIT_INVALID: '" in source)
print(f'Checks passed: {tests}/{tests}')
