"""Live three-domain investigation; existing MCP reader and finance investigator only."""
import asyncio,argparse,json,sys
from agent.phase5_2c_three_domain import investigate
from agent.phase4c7_adaptive import adaptive_investigation
from agent.phase4c6_nl_investigation import GeminiInvestigationInterpreter
from agent.phase4b57_nl_dynamic_finance import mcp_query

async def run(q):
    from mcp import Client
    from mcp_server.server import mcp
    interpreter=GeminiInvestigationInterpreter()
    async with Client(mcp) as client:
        async def reader(sql,purpose):return await mcp_query(client,sql,purpose)
        async def finance(question,rd):return await adaptive_investigation(question,interpreter,rd)
        return await investigate(q,reader,finance)

def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('question',nargs='?',default='Compare finance, late delivery and review scores from February 2018 to March 2018')
    a=ap.parse_args()
    try:
        result=asyncio.run(run(a.question))
        print(json.dumps(result,indent=2,ensure_ascii=False,default=str))
        return 0
    except Exception as ex:
        while isinstance(ex,BaseExceptionGroup) and ex.exceptions:ex=ex.exceptions[0]
        print(json.dumps({'status':'THREE_DOMAIN_NOT_VALIDATED','error_type':type(ex).__name__,'reason':str(ex)[:500],'approved_for_mcp':False,'causal_claim':False},indent=2))
        return 1
if __name__=='__main__':sys.exit(main())
