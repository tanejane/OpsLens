from __future__ import annotations
import asyncio, sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path: sys.path.insert(0,str(ROOT))
from agent.investigator_phase3g import LLMPlannerInvestigator
from agent.planner_contract import PlannerDecision
from agent.planner_providers import FakePlannerProvider
from agent.proposal_compiler import ProposalRejected, compile_proposal

async def main():
    print('='*104); print('OPSLENS PHASE 3G — PROVIDER-ABSTRACTED LLM PLANNER VALIDATION'); print('='*104)
    r=await LLMPlannerInvestigator(FakePlannerProvider()).run('Why did profit drop even though sales went up?')
    print('\nPlanner decisions:')
    for i,d in enumerate(r['planner_trace'],1): print(f"  {i}. {d['action_type']} {d.get('hypothesis_id') or '-'} | confidence={d['confidence']}")
    print('\nGoverned tool sequence:')
    for x in r['tool_trace']: print(f"  - {x['action_id']}: {x['tool']} -> ok={x['ok']}")
    print('\nHypotheses:',{k:v['status'] for k,v in r['hypotheses'].items()}); print('Stop reason:',r['stop_reason']); print('Conclusion:',r['conclusion'])
    checks=[]; add=lambda n,o,v: checks.append((n,bool(o),v))
    add('Planner emitted typed decisions',all('action_type' in d and 'rationale' in d for d in r['planner_trace']),[d['action_type'] for d in r['planner_trace']])
    add('Application compiled planner decisions into governed MCP calls',len(r['tool_trace'])>=8,[x['action_id'] for x in r['tool_trace']])
    add('Planner never authored raw SQL',all(not(d.get('query_hint') and 'select ' in d['query_hint'].lower()) for d in r['planner_trace']),[d.get('query_hint') for d in r['planner_trace']])
    add('All governed tool calls succeeded',all(x['ok'] for x in r['tool_trace']),[(x['action_id'],x['ok']) for x in r['tool_trace']])
    add('All four hypotheses evidence-resolved',all(h['status'] in {'SUPPORTED','WEAK','REJECTED'} for h in r['hypotheses'].values()),{k:v['status'] for k,v in r['hypotheses'].items()})
    add('Planner stopped voluntarily after evidence resolution',r['stop_reason']=='PLANNER_STOP',r['stop_reason'])
    unsafe=False
    try: PlannerDecision(action_type='knowledge_search',hypothesis_id='H1',evidence_needed='Search.',rationale='Unsafe test.',query_hint='SELECT * FROM staging.secret_data;',confidence=.9)
    except Exception: unsafe=True
    add('Raw-SQL planner payload rejected by typed contract',unsafe,unsafe)
    premature=False
    try:
        d=PlannerDecision(action_type='stop',evidence_needed='Stop.',rationale='Premature.',confidence=.9)
        compile_proposal(d,{'hypotheses':{'H1':{'status':'SUPPORTED'},'H2':{'status':'UNTESTED'},'H3':{'status':'UNTESTED'},'H4':{'status':'UNTESTED'}},'evidence_ledger':[]})
    except ProposalRejected: premature=True
    add('Premature planner stop rejected by application',premature,premature)
    print('\nValidation:'); passed=0
    for n,o,v in checks: print(f"[{'PASS' if o else 'FAIL'}] {n}: {v}"); passed+=int(o)
    print(f'\nChecks passed: {passed}/{len(checks)}'); verdict='PASS' if passed==len(checks) else 'REVIEW'; print('VERDICT:',verdict)
    if verdict!='PASS': raise SystemExit(1)
if __name__=='__main__': asyncio.run(main())
