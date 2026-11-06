"""Live MCP smoke test for all governed satisfaction metrics. No permission mutations."""
import argparse
import asyncio
import json
import sys
from decimal import Decimal
from agent.phase4c11_satisfaction import METRICS, measure
from agent.phase4b57_nl_dynamic_finance import mcp_query

async def execute(start, end):
    from mcp import Client
    from mcp_server.server import mcp
    measurements={}
    async with Client(mcp) as client:
        async def reader(sql,purpose):
            return await mcp_query(client,sql,purpose)
        for metric in METRICS:
            measurements[metric] = await measure(metric,start,end,reader)
    populations=[r['population'] for r in measurements.values()]
    if any(p != populations[0] for p in populations[1:]):
        raise ValueError('MCP metric requests returned inconsistent populations')
    return {'status':'LIVE_MCP_VALIDATED','period':[start,end],
            'source':'semantic.order_review_evidence_v1',
            'population':populations[0],
            'metrics':{k:{'value':v['value'],'unit':v['unit']} for k,v in measurements.items()},
            'causal_claim':False,'limitations':measurements['average_review_score']['limitations']}

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('start',nargs='?',default='2018-06-01')
    p.add_argument('end',nargs='?',default='2018-07-01')
    args=p.parse_args()
    try:
        from agent.phase4c11_satisfaction import period
        period(args.start,args.end)
        result=asyncio.run(execute(args.start,args.end))
    except Exception as exc:
        while isinstance(exc,BaseExceptionGroup) and exc.exceptions:
            exc=exc.exceptions[0]
        print(json.dumps({'status':'LIVE_MCP_NOT_VALIDATED','error_type':type(exc).__name__,
            'reason':str(exc)[:700], 'next_step':'Check MCP SQL allowlist, view permissions and reader output; do not bypass authorization.'},indent=2))
        return 1
    print(json.dumps(result,indent=2))
    return 0
if __name__=='__main__':sys.exit(main())
