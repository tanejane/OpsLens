"""Live MCP smoke check for four delivery metrics, fail closed."""
import argparse, asyncio, json, sys
from agent.phase4c15_delivery import METRICS, measure, period
from agent.phase4b57_nl_dynamic_finance import mcp_query
async def execute(start,end):
    from mcp import Client
    from mcp_server.server import mcp
    async with Client(mcp) as client:
        async def reader(sql,purpose):return await mcp_query(client,sql,purpose)
        values={}
        for k in METRICS:values[k]=await measure(k,start,end,reader)
    populations=[v['population'] for v in values.values()]
    if any(p!=populations[0] for p in populations[1:]):raise ValueError('Inconsistent MCP populations')
    return {'status':'LIVE_MCP_VALIDATED','source':'semantic.order_delivery_evidence_v1','period':[start,end],'population':populations[0],'metrics':{k:{'value':v['value'],'unit':v['unit']} for k,v in values.items()},'causal_claim':False,'limitations':values['late_delivery_rate']['limitations']}
def main():
    p=argparse.ArgumentParser();p.add_argument('start',nargs='?',default='2018-06-01');p.add_argument('end',nargs='?',default='2018-07-01');a=p.parse_args()
    try:period(a.start,a.end);result=asyncio.run(execute(a.start,a.end))
    except Exception as exc:
        while isinstance(exc,BaseExceptionGroup) and exc.exceptions:exc=exc.exceptions[0]
        print(json.dumps({'status':'LIVE_MCP_NOT_VALIDATED','error_type':type(exc).__name__,'reason':str(exc)[:600],'next_step':'Review MCP policy and role permissions; do not bypass authorization.'},indent=2));return 1
    print(json.dumps(result,indent=2));return 0
if __name__=='__main__':sys.exit(main())
