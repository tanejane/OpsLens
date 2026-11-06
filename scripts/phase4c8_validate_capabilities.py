"""Offline tests for 4C.8. No DB, Gemini or MCP required."""
import asyncio
from types import SimpleNamespace
from agent.phase4c8_capabilities import REGISTRY, registry_snapshot, find_capability
from agent.phase4c8_planning import PlanningRequest, PlanningRejected, plan, audit_registry

checks = 0
def check(name, test):
    global checks
    assert test, name
    checks += 1
    print('PASS:',name)

check('registry audit', audit_registry()['status']=='REGISTRY_VALID')
check('metadata snapshot',len(registry_snapshot())==8)
check('known capability',find_capability('finance_premise').status=='available')
check('unknown capability',find_capability('unknown') is None)
check('delivery not connected',find_capability('delivery_diagnostics').executor is None)
check('review not connected',find_capability('review_diagnostics').executor is None)
check('incrementality ungoverned',find_capability('campaign_incrementality').status=='not_governed')
check('category financial allocation ungoverned',find_capability('category_profitability').status=='not_governed')
check('no invented periods',plan(PlanningRequest('financial_divergence'))['status']=='NEEDS_CLARIFICATION')
check('no steps before periods',not plan(PlanningRequest('financial_divergence'))['steps'])
p=plan(PlanningRequest('financial_divergence',True))
check('finance plan executable only through existing executor',p['status']=='READY_FOR_EXISTING_EXECUTOR')
check('full finance steps',len(p['steps'])==3)
check('step cap',len(plan(PlanningRequest('financial_divergence',True,1))['steps'])==1)
check('separate graph authorization',plan(PlanningRequest('ranking',True))['status']=='DELEGATE_TO_GOVERNED_GRAPH_PLANNER')
check('delivery blocked',plan(PlanningRequest('delivery_issue',True))['status']=='INSUFFICIENT_GOVERNED_CAPABILITIES')
check('marketing blocked',not plan(PlanningRequest('marketing_effectiveness',True))['executable'])
check('product mix blocked',not plan(PlanningRequest('product_mix_profit',True))['executable'])
check('review blocked',not plan(PlanningRequest('satisfaction_issue',True))['executable'])
check('unknown intent blocked',plan(PlanningRequest('arbitrary_intent',True))['status']=='UNSUPPORTED_INTENT')
check('no causal privilege',all(plan(PlanningRequest(i,True))['causal_claim'] is False for i in ('financial_divergence','ranking','delivery_issue','marketing_effectiveness')))
for bad in (0,4,True,1.5):
    try:
        plan(PlanningRequest('financial_divergence',True,bad))
    except PlanningRejected:
        check('invalid budget '+str(bad),True)
    else:
        raise AssertionError('Invalid budget was accepted')
try:
    plan(PlanningRequest('financial_divergence','yes',1))
except PlanningRejected:
    check('invalid period flag blocked',True)
else:
    raise AssertionError('Invalid period flag was accepted')
print(f'Checks passed: {checks}/{checks}')
