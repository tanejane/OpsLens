"""Offline deterministic contract tests; does not access database or Gemini."""
import asyncio
from unittest.mock import patch
from agent.phase4c3_investigation import (InvestigationRequest, InvestigationState, InvestigationRejected,
                                          validate_request, verify_premise,decompose,compose,collect_evidence)

def fixture(rev0=844178.71,rev1=983213.44,profit0=115103.05,profit1=66524.92,cogs0=580000,cogs1=636445.53):
    vals={'effective_revenue':(rev0,rev1),'effective_contribution_profit':(profit0,profit1),'effective_cogs':(cogs0,cogs1)}
    def e(x,period):return {'value':str(x),'status':'MEASURED_WITH_SCOPE_LIMITS','source':'semantic.order_economics','period_reconciliation_status':'RECONCILED_FOR_REVIEW','source_population_rows':100,'period':period}
    return {k:{'before':e(v[0],['2018-02-01','2018-03-01']),'measurement':e(v[1],['2018-03-01','2018-04-01']),'causal_claim':False} for k,v in vals.items()}

def check(label,fn):
    fn();print('PASS:',label)

def raises(f):
    try:f()
    except InvestigationRejected:return
    raise AssertionError('Expected block')

def one():return InvestigationRequest('2018-02-01','2018-03-01','2018-03-01','2018-04-01')

def core():
    s=InvestigationState(one(),observations=fixture())
    verify_premise(s);decompose(s);compose(s)
    return s

async def async_cases():
    calls=[]
    async def fake(metric,before,after,reader):
        calls.append(metric)
        return fixture()[metric]
    s=InvestigationState(one())
    with patch('agent.phase4c3_investigation.finance_execute',fake):
        await collect_evidence(s,lambda *_:None)
    assert calls==['effective_revenue','effective_contribution_profit','effective_cogs']
    print('PASS: three audited governed metric calls')
    assert len(s.observations)==3
    print('PASS: evidence registry populated')
    async def bad(metric,before,after,reader):
        x=fixture()[metric].copy()
        x['before']=dict(x['before'],source='staging.order_profitability')
        return x
    with patch('agent.phase4c3_investigation.finance_execute',bad):
        try:await collect_evidence(InvestigationState(one()),lambda *_:None)
        except InvestigationRejected:pass
        else:raise AssertionError('Invalid source accepted')
    print('PASS: wrong source blocked')

def assert_true(x):
    assert x

if __name__=='__main__':
    check('chronological dates allowed',lambda:validate_request(one()))
    check('overlapping periods blocked',lambda:raises(lambda:validate_request(InvestigationRequest('2018-03-01','2018-04-01','2018-03-20','2018-05-01'))))
    check('unregistered focus blocked',lambda:raises(lambda:validate_request(InvestigationRequest('2018-02-01','2018-03-01','2018-03-01','2018-04-01','marketing'))))
    s=core()
    check('divergence verified',lambda:assert_true(s.premise['divergence_confirmed']))
    check('no causal claim',lambda:assert_true(s.result['causal_claim'] is False))
    check('balanced bridge',lambda:assert_true(sum(float(x['contribution_to_profit_delta']) for x in s.findings)-float(s.premise['contribution_profit_delta'])<0.000001))
    check('explicit residual limitations',lambda:assert_true('NOT a verified' in s.findings[2]['limitation']))
    check('three provenance records',lambda:assert_true(len(s.result['evidence'])==3))
    s2=InvestigationState(one(),observations=fixture(rev1=700000,profit1=140000))
    verify_premise(s2);decompose(s2);compose(s2)
    check('false premise not confirmed',lambda:assert_true(s2.result['status']=='PREMISE_NOT_CONFIRMED'))
    check('hypotheses not asserted',lambda:assert_true(len(s.result['hypotheses_not_tested'])>0))
    asyncio.run(async_cases())
    print('Checks passed: 13/13')

def assert_true(x):assert x
