"""Live read-only MCP verification of five registered product/category metrics."""
import argparse
import asyncio
import json
import sys
from agent.phase4c19_product import METRICS, compile_metric, measure
from agent.phase4b57_nl_dynamic_finance import mcp_query

async def execute(start, end, category):
    from mcp import Client
    from mcp_server.server import mcp
    results = {}
    async with Client(mcp) as client:
        async def reader(sql, purpose):
            return await mcp_query(client, sql, purpose)
        for metric in METRICS:
            results[metric] = await measure(metric, start, end, category, reader)
    anchor = results[next(iter(METRICS))]
    for k, result in results.items():
        for field in ('source', 'category', 'period', 'policy', 'time_basis', 'population', 'total_item_gmv', 'category_item_gmv'):
            if result[field] != anchor[field]:
                raise ValueError(f'Cross-metric reconciliation failed for {k}.{field}')
    return {'status':'LIVE_MCP_VALIDATED','period':[start,end],'category':category,
        'source':anchor['source'], 'population':anchor['population'],
        'total_item_gmv':anchor['total_item_gmv'], 'category_item_gmv':anchor['category_item_gmv'],
        'policy':anchor['policy'], 'time_basis':anchor['time_basis'],
        'metrics':{k:{'value':r['value'],'unit':r['unit']} for k,r in results.items()},
        'causal_claim':False,'inventory_claim_allowed':False,'limitations':anchor['limitations']}

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('start',nargs='?',default='2018-06-01')
    parser.add_argument('end',nargs='?',default='2018-07-01')
    parser.add_argument('category',nargs='?',default='health_beauty')
    args=parser.parse_args()
    try:
        compile_metric('units_sold',args.start,args.end,args.category)
        value=asyncio.run(execute(args.start,args.end,args.category))
    except Exception as exc:
        while isinstance(exc,BaseExceptionGroup) and exc.exceptions:
            exc=exc.exceptions[0]
        print(json.dumps({'status':'LIVE_MCP_NOT_VALIDATED','error_type':type(exc).__name__,
            'reason':str(exc)[:700], 'next_step':'Check policy and role independently; do not bypass MCP authorization.'},indent=2))
        return 1
    print(json.dumps(value,indent=2))
    return 0
if __name__=='__main__':sys.exit(main())
