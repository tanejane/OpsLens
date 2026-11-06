from pathlib import Path
from dataclasses import replace
from agent.phase4b43_graph_planner import GraphPlanner,AnalysisRequest,PlanningRejected

ROOT=Path(__file__).resolve().parents[1]
AUDIT=ROOT/'reports'/'phase4b42_relationship_audit.json'
p=GraphPlanner(AUDIT)
base=AnalysisRequest('unique_orders',('seller_id',),'2018-01-01','2019-01-01',limit=5)
checks=[]
def assert_contains(text,parts):
    for part in parts: assert part in text, (part,text)
def ok(name,fn):
    fn();checks.append(name);print('PASS:',name)
def reject(name,fn,needle):
    try:fn()
    except PlanningRejected as e:
        assert needle.lower() in str(e).lower(),str(e)
        checks.append(name);print('PASS:',name)
    else:raise AssertionError('Expected rejection: '+name)
ok('Audited seller path with correct DISTINCT order grain',lambda:assert_contains(p.compile(base)['sql'],['COUNT(DISTINCT t0."order_id")','"commerce"."order_items"','JOIN','LIMIT 5']))
ok('Metric-specific fanout safety disclosed',lambda:assert_contains(p.compile(base)['safety'],['fanout']))
ok('Governed June gross margin is ratio of sums',lambda:assert_contains(p.compile(AnalysisRequest('gross_margin_pct',(), '2018-06-01','2018-07-01'))['sql'],['SUM(t0."revenue")','SUM(t0."cogs")','NULLIF']))
reject('Cannot substitute category gross margin',lambda:p.compile(AnalysisRequest('gross_margin_pct',('category',),'2018-06-01','2018-07-01')),'not allowed')
reject('Incident-only margin is not treated as canonical',lambda:p.compile(AnalysisRequest('incident_gross_margin_pct',('incident_category',),'2018-06-01','2018-07-01')),'incident-specific')
reject('Cannot invent metrics',lambda:p.compile(replace(base,metric='random_margin')),'unknown metric')
reject('Reject ambiguous dates',lambda:p.compile(replace(base,end_date_exclusive=None)),'explicit')
reject('Reject invalid sort',lambda:p.compile(replace(base,order='sideways')),'sort')
reject('Reject invalid limit',lambda:p.compile(replace(base,limit=5000)),'limit')
modified=p.audit['relationships']['orders_to_items']['status'];p.audit['relationships']['orders_to_items']['status']='TIMEOUT'
reject('Timeout cannot authorize edge',lambda:p.compile(base),'not structurally verified')
p.audit['relationships']['orders_to_items']['status']=modified
print(f'Checks passed: {len(checks)}/{len(checks)}')
