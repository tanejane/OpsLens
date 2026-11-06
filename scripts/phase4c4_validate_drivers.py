"""Offline tests for Phase 4C.4 governed driver discovery."""
from __future__ import annotations
import asyncio, copy
from decimal import Decimal
from agent.phase4c4_drivers import (FIELDS, COMPONENTS, DriverRejected,
    compile_components, validate_components, discover_drivers)

passed=0

def check(title,fn):
    global passed
    fn();passed+=1;print('PASS:',title)

def rejects(fn):
    try:fn()
    except DriverRejected:return
    raise AssertionError('Expected fail-closed rejection')

PERIODS={'before':['2018-02-01','2018-03-01'],'after':['2018-03-01','2018-04-01']}
BEFORE={'effective_revenue':'844178.71','effective_cogs':'537019.4345','effective_contribution_profit':'115103.045692',
        'refund_amount':'30000','fulfillment_cost':'60000','payment_processing_cost':'24000','marketing_cost_effective':'58000','incentive_cost_effective':'15000'}
AFTER={'effective_revenue':'983213.44','effective_cogs':'636445.5252','effective_contribution_profit':'66524.916768',
        'refund_amount':'40000','fulfillment_cost':'66000','payment_processing_cost':'28000','marketing_cost_effective':'90000','incentive_cost_effective':'17000'}
for d in (BEFORE,AFTER):
    d['other_adjustments_residual']=str(Decimal(d['effective_revenue'])-Decimal(d['effective_cogs'])-Decimal(d['effective_contribution_profit'])-sum((Decimal(d[k]) for k in COMPONENTS[:-1]), Decimal(0)))

def response(moment):
    d=BEFORE if moment=='before' else AFTER
    return {'rows':[{'eligible_source_rows':6694 if moment=='before' else 7188,
                     'distinct_orders':6694 if moment=='before' else 7188,**d}]}

def proofs(moment):
    d=BEFORE if moment=='before' else AFTER
    return {k:{'source':'semantic.order_economics','period':PERIODS[moment],
               'status':'MEASURED_WITH_SCOPE_LIMITS','period_reconciliation_status':'RECONCILED_FOR_REVIEW',
               'source_population_rows':6694 if moment=='before' else 7188,'value':d[k]} for k in FIELDS[:3]}

def core():
    br=Decimal(BEFORE['effective_revenue'])-Decimal(BEFORE['effective_cogs'])-Decimal(BEFORE['effective_contribution_profit'])
    ar=Decimal(AFTER['effective_revenue'])-Decimal(AFTER['effective_cogs'])-Decimal(AFTER['effective_contribution_profit'])
    return {'route':'investigation','executable':True,'causal_claim':False,'periods':PERIODS,
        'findings':[{'component':'other_net_charges_residual','delta':str(ar-br)}],
        'evidence':{k:{moment:proofs(moment)[k] for moment in ('before','after')} for k in FIELDS[:3]}}

async def test_success():
    count=0
    async def reader(sql,purpose):
        nonlocal count
        assert '"semantic"."order_cost_components"' in sql
        moment='before' if '2018-02-01' in sql else 'after'
        count+=1
        return response(moment)
    output=await discover_drivers(core(),reader)
    assert output['driver_discovery']['status']=='RECONCILED_COMPONENT_BREAKDOWN'
    assert count==2 and len(output['driver_discovery']['components'])==6
    assert output['driver_discovery']['causal_claim'] is False

async def test_unavailable():
    async def missing(sql,purpose):return {'ok':False,'error':'relation does not exist'}
    output=await discover_drivers(core(),missing)
    assert output['driver_discovery']['status']=='DRIVER_EVIDENCE_UNAVAILABLE'
    assert output['findings'][0]['component']=='other_net_charges_residual'

async def test_tampered_bridge():
    c=core();c['findings'][0]['delta']='0'
    async def reader(sql,purpose):return response('before' if '2018-02-01' in sql else 'after')
    output=await discover_drivers(c,reader)
    assert output['driver_discovery']['status']=='DRIVER_EVIDENCE_UNAVAILABLE'

async def test_no_direct_calls():
    async def reader(sql,purpose):raise AssertionError('Should not call MCP')
    try:await discover_drivers({'route':'ranking'},reader)
    except DriverRejected:pass
    else:raise AssertionError('Expected blocked noninvestigation')

def run():
    check('approved semantic view only',lambda:assert_true('"semantic"."order_cost_components"' in compile_components(*PERIODS['before'])))
    check('half-open dates',lambda:assert_true("< DATE '2018-03-01'" in compile_components(*PERIODS['before'])))
    check('no SQL injection from periods',lambda:assert_true(raises_any(lambda:compile_components("2018-02-01'; DROP TABLE x",'2018-03-01'))))
    check('one aggregate row valid',lambda:assert_true(validate_components(response('before'),tuple(PERIODS['before']),proofs('before'))['source_population_rows']==6694))
    check('source mismatch blocked',lambda:rejects(lambda:validate_components(response('before'),tuple(PERIODS['after']),proofs('before'))))
    check('finance total mismatch blocked',lambda:rejects(lambda:validate_components(response('before'),tuple(PERIODS['before']),{**proofs('before'),'effective_revenue':{**proofs('before')['effective_revenue'],'value':'1'}})))
    check('population mismatch blocked',lambda:rejects(lambda:validate_components({**response('before'),'rows':[{**response('before')['rows'][0],'eligible_source_rows':10}]},tuple(PERIODS['before']),proofs('before'))))
    check('duplicate order grain blocked',lambda:rejects(lambda:validate_components({**response('before'),'rows':[{**response('before')['rows'][0],'distinct_orders':10}]},tuple(PERIODS['before']),proofs('before'))))
    check('bad component identity blocked',lambda:rejects(lambda:validate_components({**response('before'),'rows':[{**response('before')['rows'][0],'refund_amount':'0'}]},tuple(PERIODS['before']),proofs('before'))))
    check('missing metric blocked',lambda:rejects(lambda:validate_components({'rows':[{'eligible_source_rows':6694,'distinct_orders':6694}]},tuple(PERIODS['before']),proofs('before'))))
    check('nonfinite components blocked',lambda:rejects(lambda:validate_components({**response('before'),'rows':[{**response('before')['rows'][0],'refund_amount':'NaN'}]},tuple(PERIODS['before']),proofs('before'))))
    check('mcp rejection blocked',lambda:rejects(lambda:validate_components({'ok':False},tuple(PERIODS['before']),proofs('before'))))
    check('successfully reconciles two periods',lambda:asyncio.run(test_success()))
    check('missing view is classified as unavailable',lambda:asyncio.run(test_unavailable()))
    check('tampered prior investigation blocked',lambda:asyncio.run(test_tampered_bridge()))
    check('unsupported route performs no SQL',lambda:asyncio.run(test_no_direct_calls()))
    print(f'Checks passed: {passed}/{passed}')

def assert_true(value):assert value

def raises_any(fn):
    try:fn()
    except (ValueError,TypeError):return True
    return False
if __name__=='__main__':run()
