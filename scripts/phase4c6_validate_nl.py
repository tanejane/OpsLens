"""Offline contract tests for 4C.6; no Gemini, DB, or MCP required."""
import asyncio
from unittest.mock import patch
from agent.phase4c6_nl_investigation import (Interpretation,ground_interpretation,
    explicit_periods,run_investigation)

PASSED=0

def assert_value(value):
    assert value

def check(label, fn):
    global PASSED
    fn()
    PASSED+=1
    print('PASS:', label)

Q='Why did revenue rise but contribution profit fall in March 2018 compared with February 2018?'
OK=Interpretation('diagnostic_investigation',before_start='2018-02-01',before_end='2018-03-01',
                  after_start='2018-03-01',after_end='2018-04-01')

def good():
    req,err=ground_interpretation(Q,OK)
    assert err is None and req.before_start=='2018-02-01' and req.after_end=='2018-04-01'
check('explicit two months grounded',good)
check('December rollover',lambda: assert_value(('2018-12-01','2019-01-01') in explicit_periods('December 2018')))
check('two ISO intervals grounded',lambda: assert_value(ground_interpretation(
    'Investigate revenue profit between 2018-02-01 2018-03-01 and 2018-03-01 2018-04-01',OK)[1] is None))
check('month name case insensitive',lambda: assert_value(ground_interpretation(Q.lower(),OK)[1] is None))

CASES=[
    ('missing baseline','Why did revenue rise but profit fall in March 2018?',OK,'NEEDS_CLARIFICATION'),
    ('model invents month','Why did profit fall in January 2018 compared with March 2018?',OK,'NEEDS_CLARIFICATION'),
    ('reversed periods',Q,Interpretation('diagnostic_investigation',before_start='2018-03-01',before_end='2018-04-01',after_start='2018-02-01',after_end='2018-03-01'),'NEEDS_CLARIFICATION'),
    ('unsupported focus',Q,Interpretation('diagnostic_investigation','seller_delivery_failure',*('2018-02-01','2018-03-01','2018-03-01','2018-04-01')),'UNSUPPORTED_INVESTIGATION'),
    ('non-investigation',Q,Interpretation('other'),'UNSUPPORTED_INVESTIGATION'),
    ('missing LLM fields',Q,Interpretation('diagnostic_investigation'),'NEEDS_CLARIFICATION'),
    ('invalid dates',Q,Interpretation('diagnostic_investigation',before_start='2018-02-40',before_end='2018-03-01',after_start='2018-03-01',after_end='2018-04-01'),'NEEDS_CLARIFICATION'),
    ('unapproved inferred year','Compare February with March 2018: why profit fell?',OK,'NEEDS_CLARIFICATION'),
    ('three months ambiguous',Q+' Also April 2018.',OK,'NEEDS_CLARIFICATION'),
    ('unsupported prefix',Q,Interpretation('diagnostic_investigation', before_start='2018-02-01',before_end='2018-03-01',after_start='2018-03-01',after_end='2018-04-01',focus='marketing_incrementality'),'UNSUPPORTED_INVESTIGATION'),
]
for label,q,p,status in CASES:
    check(label,lambda q=q,p=p,status=status: assert_value(ground_interpretation(q,p)[1]['status']==status))

class DummyInterpreter:
    def __init__(self, p):self.p=p
    def interpret(self,q):return self.p

async def run_no_db():
    async def no_sql(*args):raise AssertionError('SQL called on ungrounded query')
    result=await run_investigation('Why did profit fall in March 2018?',DummyInterpreter(OK),no_sql)
    assert result['status']=='NEEDS_CLARIFICATION' and not result['executable']
check('no MCP call on missing baseline',lambda:asyncio.run(run_no_db()))

async def run_faux():
    calls=[]
    async def mock_core(req,reader):
        calls.append(('core',req.before_start,req.after_start))
        return {'route':'investigation','periods':{'before':[req.before_start,req.before_end], 'after':[req.after_start,req.after_end]},'premise':{'divergence_confirmed':False},'status':'PREMISE_NOT_CONFIRMED'}
    async def mock_drivers(core,reader):
        result=await reader('mock SQL','components')
        assert result=={'rows':[{'eligible_source_rows':10}]}
        calls.append(('drivers',))
        return {**core,'driver_discovery':{'status':'RECONCILED_COMPONENT_BREAKDOWN'}}
    def mock_evaluate(enriched,*,max_hypotheses):
        calls.append(('evaluate',max_hypotheses))
        return {'status':'EVIDENCE_RANKED_NOT_CAUSAL','causal_claim':False,'hypotheses':[]}
    async def reader(sql,purpose):return {'eligible_source_rows':10}
    with (patch('agent.phase4c6_nl_investigation.investigate',mock_core),
          patch('agent.phase4c6_nl_investigation.discover_drivers',mock_drivers),
          patch('agent.phase4c6_nl_investigation.evaluate_hypotheses',mock_evaluate)):
        out=await run_investigation(Q,DummyInterpreter(OK),reader,max_hypotheses=3)
    assert [t[0] for t in calls]==['core','drivers','evaluate']
    assert out['premise']['divergence_confirmed'] is False
    assert out['status']=='EVIDENCE_RANKED_NOT_CAUSAL' and out['causal_claim'] is False
check('valid question executes core then cost bridge then evaluator',lambda: asyncio.run(run_faux()))

async def no_context_mutation():
    from agent.phase4c6_unified_dispatch import dispatch
    from agent.phase4c2_graph_routing import UnifiedContext
    from agent.phase4c1_router import RoutingProposal
    class Router:
        def propose(self,*args):return RoutingProposal('investigate',('diagnostic_investigation',))
    ctx=UnifiedContext()
    async def no_sql(*args):raise AssertionError('SQL on missing baseline')
    result,new=await dispatch('Why did our profit fall in March 2018?',ctx,Router(),None,no_sql,None,None,None,DummyInterpreter(OK))
    assert new==ctx and result['status']=='NEEDS_CLARIFICATION'
check('unified investigation clarification preserves state',lambda:asyncio.run(no_context_mutation()))
print(f'Checks passed: {PASSED}/{PASSED}')
