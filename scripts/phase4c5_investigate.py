"""Phase 4C.5 live demo: audited core + verified components + ranked hypotheses.

python -m scripts.phase4c5_investigate 2018-02-01 2018-03-01 2018-03-01 2018-04-01
"""
import argparse
import asyncio
import json
from agent.phase4b57_nl_dynamic_finance import mcp_query
from agent.phase4c3_investigation import InvestigationRequest, investigate
from agent.phase4c4_drivers import discover_drivers
from agent.phase4c5_hypotheses import evaluate_hypotheses

async def main():
    parser=argparse.ArgumentParser()
    for part in ('before_start','before_end','after_start','after_end'):
        parser.add_argument(part)
    parser.add_argument('--top',type=int,default=5)
    args=parser.parse_args()
    from mcp import Client
    from mcp_server.server import mcp
    async with Client(mcp) as client:
        async def reader(sql,purpose):
            return await mcp_query(client,sql,purpose)
        async def component_reader(sql,purpose):
            row=await reader(sql,purpose)
            if not isinstance(row,dict):
                raise TypeError('Invalid MCP aggregate row')
            return {'rows':[row]}
        core=await investigate(InvestigationRequest(args.before_start,args.before_end,args.after_start,args.after_end),reader)
        enriched=await discover_drivers(core,component_reader)
        evaluation=evaluate_hypotheses(enriched,max_hypotheses=args.top)
    print(json.dumps({'investigation_status':enriched['status'],
                      'driver_discovery_status':enriched['driver_discovery']['status'],
                      'premise':enriched['premise'],
                      'hypothesis_evaluation':evaluation},indent=2,default=str))

if __name__=='__main__':
    try:
        asyncio.run(main())
    except Exception as exc:
        while isinstance(exc,BaseExceptionGroup) and exc.exceptions:
            exc=exc.exceptions[0]
        print('BLOCKED:',type(exc).__name__,str(exc)[:450])
        raise SystemExit(1)
