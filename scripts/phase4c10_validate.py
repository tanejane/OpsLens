from copy import deepcopy
from agent.phase4c10_contract import assess
base={'version':'4c10.1','read_only':True,'mcp_authorized':False,'policy':'mean_non_null_effective_scores_per_order','time_basis':'purchase_month',
'source':{'orders':4,'unique_orders':4},'reviews':{'review_rows':4,'bad_scores':0,'reviewed_ids':3},
'evidence':{'rows':4,'unique_rows':4,'null_keys':0,'missing_purchase_dates':0,'reviewed_orders':3,'low_rating_orders':1,'multiple_review_orders':1,'aggregated_review_rows':4,'mismatched_scores':0,'mismatched_flags':0},
'months':[{'month':'2018-02','orders':4,'reviewed_orders':3,'low_rating_orders':1}]}
checks=[]
def check(name,fn=None,expected='ORDER_REVIEW_CONTRACT_BLOCKED',raises=False):
    a=deepcopy(base)
    if fn:fn(a)
    try:
        z=assess(a);ok=not raises and z['status']==expected and not z['approved_for_mcp'] and not z['causal_claim']
    except (ValueError,TypeError,KeyError):ok=raises
    checks.append(ok);print(('PASS' if ok else 'FAIL')+': '+name)
check('valid audit',expected='ORDER_REVIEW_GRAIN_VALIDATED')
check('duplicate order',lambda a:a['source'].update(unique_orders=3))
check('missing order',lambda a:a['evidence'].update(rows=3))
check('null order key',lambda a:a['evidence'].update(null_keys=1))
check('raw review discrepancy',lambda a:a['evidence'].update(aggregated_review_rows=5))
check('invalid scores',lambda a:a['reviews'].update(bad_scores=1))
check('wrong aggregation',lambda a:a['evidence'].update(mismatched_scores=1))
check('wrong flags',lambda a:a['evidence'].update(mismatched_flags=1))
check('impossible reviewed count',lambda a:a['evidence'].update(reviewed_orders=5))
check('impossible low count',lambda a:a['evidence'].update(low_rating_orders=4))
check('monthly mismatch',lambda a:a['months'][0].update(orders=3))
check('policy tampering',lambda a:a.update(policy='latest'),raises=True)
check('permission tampering',lambda a:a.update(mcp_authorized=True),raises=True)
check('time tampering',lambda a:a.update(time_basis='submission_month'),raises=True)
check('bool count',lambda a:a['source'].update(orders=True),raises=True)
check('bad month',lambda a:a['months'][0].update(month='April'),raises=True)
print(f'Checks passed: {sum(checks)}/{len(checks)}')
if not all(checks):raise SystemExit(1)
