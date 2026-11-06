from __future__ import annotations
import sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from agent.phase4a_context import build_context,sample_catalog
from agent.phase4a_planner import OfflinePlanProvider
from agent.phase4a_plan_contract import validate_plan,PlanRejected

QUESTIONS = [
    'Why did revenue increase while profit fell in March 2018?',
    'Which sellers are contributing to late delivery?',
    'Are stockouts reducing revenue?',
    'Why are refunds and bad reviews increasing?',
    'Why are shoppers abandoning checkout?',
]
metrics,relations=sample_catalog()
provider=OfflinePlanProvider()
plans=[]
for q in QUESTIONS:
    context=build_context(q,metrics=metrics,relations=relations)
    p=provider.create_plan(context)
    plans.append(p)
    print(f'\n{q}\n  Type: {p.investigation_type}  Environment: {p.business_environment}')
    for h in p.hypotheses:
        print(f'  {h.hypothesis_id}: {h.statement} [UNTESTED]')

checks=[]
def add(n,v): checks.append((n,bool(v)))
add('Five varied questions produce distinct investigation types',len({p.investigation_type for p in plans})==5)
add('Hypotheses vary rather than copying H1-H4 descriptions',len({h.statement for p in plans for h in p.hypotheses})==10)
add('Every hypothesis begins UNTESTED',all(h.status=='UNTESTED' for p in plans for h in p.hypotheses))
add('Every hypothesis has falsification and evidence needs',all(h.falsification_test and h.evidence_needs for p in plans for h in p.hypotheses))
add('GA4 funnel kept separate from Olist',plans[-1].business_environment=='ga4' and all(n.target_relation.startswith('behavior.') for h in plans[-1].hypotheses for n in h.evidence_needs))
ctx=build_context('Why did revenue change?',metrics=metrics,relations=relations+[{'name':'staging.secret','domain':'staging'}])
add('Disallowed schema filtered from context',all(not r['name'].startswith('staging.') for r in ctx.relation_catalog))
try:
    bad=plans[0].model_copy(deep=True);bad.hypotheses[0].evidence_needs[0].target_relation='staging.secret';validate_plan(bad,ctx)
    blocked=False
except PlanRejected: blocked=True
add('Application rejects invented/unapproved relations',blocked)
small=build_context('Why did revenue change?',metrics=metrics*30,relations=relations*30,max_chars=1500)
add('Context budget truncates large catalogs',small.truncated and small.context_chars<=1500)
print('\nVALIDATION')
for n,ok in checks: print(f"[{'PASS' if ok else 'FAIL'}] {n}")
print(f"Checks passed: {sum(ok for _,ok in checks)}/{len(checks)}")
print('VERDICT:', 'PASS' if all(ok for _,ok in checks) else 'REVIEW')
if not all(ok for _,ok in checks): raise SystemExit(1)
