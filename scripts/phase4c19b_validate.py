"""Offline checks for the Phase 4C.19B comparator (no database required)."""
from decimal import Decimal
from scripts.phase4c19b_compare import compare
from agent.phase4c19_product import compile_metric,validate_metric

def fixture():
    pg={'total_units':100,'unique_items':100,'total_orders':80,'total_gmv':'1000', 'invalid_items':0,'category_units':20,'category_unique_items':20,'category_orders':18,'category_gmv':'300','category_invalid_items':0}
    results={}
    for metric in ('category_order_count','units_sold','item_gmv','average_item_price','category_gmv_share'):
        plan=compile_metric(metric,'2018-06-01','2018-07-01','beleza_saude')
        results[metric]=validate_metric(plan,{'rows':[pg]})
    first=next(iter(results.values()))
    mcp={'status':'LIVE_MCP_VALIDATED','period':['2018-06-01','2018-07-01'], 'category':'beleza_saude','source':first['source'],'population':first['population'],'total_item_gmv':first['total_item_gmv'],'category_item_gmv':first['category_item_gmv'],'metrics':{k:{'value':v['value'],'unit':v['unit']} for k,v in results.items()},'causal_claim':False,'inventory_claim_allowed':False}
    return mcp,pg

def run():
    from copy import deepcopy
    m,p=fixture();assert compare(m,p)['status']=='MCP_POSTGRES_RECONCILED';print('PASS: valid independent reconciliation')
    cases=[('wrong period',lambda a,b:a.update(period=['2018-05-01','2018-06-01'])),('wrong category',lambda a,b:a.update(category='foo')),('unsupported inventory claim',lambda a,b:a.update(inventory_claim_allowed=True)),('unsupported causal claim',lambda a,b:a.update(causal_claim=True)),('unverified MCP',lambda a,b:a.update(status='ERROR')),('counts mismatch',lambda a,b:b.update(category_units=21)),('GMV mismatch',lambda a,b:b.update(category_gmv='301')),('average price mismatch',lambda a,b:a['metrics']['average_item_price'].update(value='16')),('share mismatch',lambda a,b:a['metrics']['category_gmv_share'].update(value='32')),('wrong unit',lambda a,b:a['metrics']['item_gmv'].update(unit='days')),('missing metric',lambda a,b:a['metrics'].pop('item_gmv')),('negative count',lambda a,b:b.update(category_units=-1)),('duplicate grain',lambda a,b:b.update(unique_items=90)),('source invalid item',lambda a,b:b.update(invalid_items=1)),('bool count',lambda a,b:b.update(category_units=True)),('wrong source',lambda a,b:a.update(source='other'))]
    for name,change in cases:
        aa,bb=deepcopy(m),deepcopy(p);change(aa,bb)
        try:compare(aa,bb)
        except (ValueError,KeyError,TypeError,ArithmeticError): print('PASS:',name)
        else:raise AssertionError('Accepted invalid fixture: '+name)
    print(f'Checks passed: {len(cases)+1}/{len(cases)+1}')
if __name__=='__main__':run()
