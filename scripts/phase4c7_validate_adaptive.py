"""Offline validation of bounded 4C.7 planner (no Gemini, Postgres or MCP)."""
import asyncio
from copy import deepcopy
from agent.phase4c7_adaptive import adaptive_investigation, AdaptiveRejected, _per_order
from agent.phase4c6_nl_investigation import Interpretation

QUESTION='Why did revenue rise and contribution profit fall in March 2018 compared with February 2018?'
class Interpreter:
    def interpret(self, question):
        return Interpretation('diagnostic_investigation', before_start='2018-02-01',before_end='2018-03-01',after_start='2018-03-01',after_end='2018-04-01')

count={'core':0,'drivers':0,'eval':0,'reader':0}

def core(confirmed=True):
    return {'route':'investigation','executable':True,'causal_claim':False,
            'status':'DESCRIPTIVE_DECOMPOSITION_ONLY' if confirmed else 'PREMISE_NOT_CONFIRMED',
            'periods':{'before':['2018-02-01','2018-03-01'],'after':['2018-03-01','2018-04-01']},
            'premise':{'divergence_confirmed':confirmed},
            'evidence':{name:{side:{'source':'semantic.order_economics','period': dates,
                'period_reconciliation_status':'RECONCILED_FOR_REVIEW',
                'source_population_rows':(100 if side=='before' else 120)}
                for side,dates in [('before',['2018-02-01','2018-03-01']),('after',['2018-03-01','2018-04-01'])]}
                for name in ('effective_revenue','effective_cogs','effective_contribution_profit')}}

def discovery(valid=True):
    return {'driver_discovery':{
        'status':'RECONCILED_COMPONENT_BREAKDOWN' if valid else 'DRIVER_EVIDENCE_UNAVAILABLE',
        'source':'semantic.order_cost_components',
        'period_evidence':{
            side:{'source':'semantic.order_cost_components','period':dates,'reconciliation':'RECONCILED_FOR_REVIEW',
                  'source_population_rows':100 if side=='before' else 120}
            for side,dates in [('before',['2018-02-01','2018-03-01']),('after',['2018-03-01','2018-04-01'])]},
        'components':[{'component':'marketing_cost_effective','before':'100','after':'180'}]}}

async def reader(*_):
    count['reader']+=1
    return {'eligible_source_rows':100}

async def fake_core(request, reader):
    count['core']+=1
    return core()

async def fake_false(request, reader):
    count['core']+=1
    return core(False)

async def fake_drivers(prior, reader):
    count['drivers']+=1
    await reader('registered SQL','cost components')
    return {**prior,**discovery()}

async def fake_missing(prior, reader):
    count['drivers']+=1
    return {**prior,**discovery(False)}

def fake_eval(prior, max_hypotheses):
    count['eval']+=1
    return {'status':'EVIDENCE_RANKED_NOT_CAUSAL','causal_claim':False,
            'hypotheses':[{'disposition':'SUPPORTS_PROFIT_PRESSURE'}], 'untested':{'campaign_incrementality':'not tested'}}

async def run(**kw):
    return await adaptive_investigation(QUESTION,Interpreter(),reader,
        investigate_fn=fake_core,driver_fn=fake_drivers,evaluate_fn=fake_eval,**kw)

def main():
    total=0
    def check(name, cond):
        nonlocal total
        assert cond,name
        total+=1
        print('PASS:',name)
    r=asyncio.run(run())
    check('reconciled adaptive path',r['status']=='EVIDENCE_RANKED_NOT_CAUSAL')
    check('three bounded steps',r['adaptive']['steps_used']==3 and len(r['adaptive']['trace'])==3)
    check('no causal claims',r['causal_claim'] is False and r['adaptive']['causal_claim'] is False)
    check('normalized comparison',r['order_normalized_evidence']['before_orders']==100 and r['order_normalized_evidence']['after_orders']==120)
    check('only one mocked component tool access',count['reader']==1)
    check('untested retained', 'campaign_incrementality' in r['adaptive']['untested'])
    count['drivers']=0
    r=asyncio.run(adaptive_investigation(QUESTION,Interpreter(),reader,investigate_fn=fake_false,driver_fn=fake_drivers,evaluate_fn=fake_eval))
    check('false premise stops',r['status']=='PREMISE_NOT_CONFIRMED' and count['drivers']==0)
    count['drivers']=0
    r=asyncio.run(run(max_steps=1))
    check('one step budget stops tools',r['status']=='PARTIAL_EVIDENCE_BUDGET' and count['drivers']==0)
    r=asyncio.run(run(max_steps=2))
    check('two step budget caps analysis',r['adaptive']['steps_used']==2 and 'order_normalized_evidence' not in r)
    r=asyncio.run(adaptive_investigation(QUESTION,Interpreter(),reader,investigate_fn=fake_core,driver_fn=fake_missing,evaluate_fn=fake_eval))
    check('missing evidence fails closed',r['status']=='INSUFFICIENT_GOVERNED_EVIDENCE')
    bad = {'source':'semantic.order_cost_components','period':['2018-02-01','2018-03-01'],
           'reconciliation':'RECONCILED_FOR_REVIEW','source_population_rows':100}
    contaminated = {**core(),**discovery()}
    contaminated['driver_discovery']['period_evidence']['before']={**bad,'source_population_rows':99}
    try:_per_order(contaminated, contaminated['driver_discovery'])
    except AdaptiveRejected: check('mismatched cohort blocked',True)
    else:raise AssertionError('mismatched cohort not blocked')
    for budget in (0,4,True):
        try:asyncio.run(run(max_steps=budget))
        except AdaptiveRejected:check('invalid budget '+str(budget),True)
        else:raise AssertionError('invalid budget allowed')
    class Ambiguous:
        def interpret(self,_):
            return Interpretation('diagnostic_investigation',before_start='2018-02-01', before_end='2018-03-01')
    prior=count['core']
    r=asyncio.run(adaptive_investigation('Why did profit fall in March 2018?',Ambiguous(),reader,investigate_fn=fake_core))
    check('ambiguous baseline no SQL',r['status']=='NEEDS_CLARIFICATION' and count['core']==prior)
    print(f'Checks passed: {total}/{total}')
if __name__=='__main__':main()
