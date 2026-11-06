"""Execute a governed investigation with explicitly supplied periods.
Example: python -m scripts.phase4c3_investigate 2018-02-01 2018-03-01 2018-03-01 2018-04-01
"""
import argparse,asyncio,json
from agent.phase4c3_investigation import InvestigationRequest,InvestigationState,build_langgraph
from agent.phase4b57_nl_dynamic_finance import mcp_query

async def main():
    parser=argparse.ArgumentParser()
    for arg in ('before_start','before_end','after_start','after_end'):parser.add_argument(arg)
    args=parser.parse_args()
    req=InvestigationRequest(args.before_start,args.before_end,args.after_start,args.after_end)
    from mcp import Client
    from mcp_server.server import mcp
    async with Client(mcp) as client:
        async def reader(sql,purpose):return await mcp_query(client,sql,purpose)
        graph=build_langgraph(reader)
        response=await graph.ainvoke({'investigation':InvestigationState(req)})
    print(json.dumps(response['investigation'].result,indent=2,default=str))
if __name__=='__main__':
    try:asyncio.run(main())
    except Exception as exc:
        while isinstance(exc,BaseExceptionGroup) and exc.exceptions:exc=exc.exceptions[0]
        print('BLOCKED:',type(exc).__name__,str(exc)[:450]);raise SystemExit(1)
