"""Offline regression tests. Does not claim live Gemini or database verification."""
from pathlib import Path
from agent.phase4b4_semantic_map import SemanticMap
from agent.phase4b44_context_grounding import Interpretation,ground,public_catalog
from agent.phase4b43_graph_planner import GraphPlanner,AnalysisRequest

def main():
    root=Path(__file__).resolve().parents[1]; m=SemanticMap()
    checks=0
    def check(label,condition):
        nonlocal checks
        assert condition,label
        checks+=1;print('PASS:',label)
    catalog=public_catalog(m)
    check('Catalog generated from live project contracts',any(x['id']=='unique_orders' for x in catalog['metrics']))
    check('Incident-only metrics hidden',all(x['source']!='semantic.product_mix_effective' for x in catalog['metrics']))
    initial=Interpretation(intent='ranking',metric_id='unique_orders',dimensions=['seller_id'],start_date='2018-06-01',end_date_exclusive='2018-07-01',order='desc',limit=5)
    r=ground(initial,m)
    check('Seller request grounded',r.status=='READY' and r.request.metric=='unique_orders')
    next_month=Interpretation(intent='ranking',start_date='2018-07-01',end_date_exclusive='2018-08-01',inherit=['metric','dimensions','order','limit'])
    r2=ground(next_month,m,r.request)
    check('Follow-up changes only period',r2.status=='READY' and r2.request.dimensions==('seller_id',) and r2.request.limit==5 and r2.request.start_date=='2018-07-01')
    bottom=Interpretation(intent='ranking',order='asc',inherit=['metric','dimensions','period','limit'])
    r3=ground(bottom,m,r2.request)
    check('Follow-up changes only ranking',r3.status=='READY' and r3.request.order=='asc' and r3.request.start_date=='2018-07-01')
    check('No prior state cannot inherit',ground(next_month,m).status=='NEEDS_CLARIFICATION')
    check('Ambiguous best sellers asks clarification',ground(Interpretation(intent='clarification',ambiguity='Performance metric unspecified.'),m).status=='NEEDS_CLARIFICATION')
    check('Unregistered metric blocked',ground(Interpretation(intent='ranking',metric_id='invented_margin',dimensions=['seller_id'],start_date='2018-06-01',end_date_exclusive='2018-07-01'),m).status!='READY')
    check('Unsupported dimension rejected',ground(Interpretation(intent='ranking',metric_id='unique_orders',dimensions=['seller_country'],start_date='2018-06-01',end_date_exclusive='2018-07-01'),m).status=='UNSUPPORTED')
    check('No implicit date',ground(Interpretation(intent='ranking',metric_id='unique_orders',dimensions=['seller_id']),m).status=='NEEDS_CLARIFICATION')
    check('Why question never yields descriptive answer',ground(Interpretation(intent='investigation',metric_id='unique_orders'),m).status=='INVESTIGATION_NOT_EXECUTED')
    check('Period comparison not silently simplified',ground(Interpretation(intent='comparison',metric_id='unique_orders',start_date='2018-06-01',end_date_exclusive='2018-07-01'),m).status=='UNSUPPORTED')
    check('Metric dimension mismatch rejected',ground(Interpretation(intent='ranking',metric_id='gross_margin_pct',dimensions=['category'],start_date='2018-06-01',end_date_exclusive='2018-07-01'),m).status=='UNSUPPORTED')
    check('Conflicting inherited period rejected',ground(Interpretation(intent='ranking',inherit=['metric','period'],start_date='2018-08-01',end_date_exclusive='2018-09-01'),m,r.request).status=='UNSUPPORTED')
    print(f'Checks passed: {checks}/{checks}')
if __name__=='__main__':main()
