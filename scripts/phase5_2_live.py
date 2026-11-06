"""Live governed MCP two-domain verification: no LLM, no new grants."""
import argparse,asyncio,json,sys
from agent.phase5_2_multidomain import investigate,MultiDomainRejected
from agent.phase4b57_nl_dynamic_finance import mcp_query

async def run(question):
    from mcp import Client
    from mcp_server.server import mcp
    async with Client(mcp) as client:
        async def reader(sql,purpose):return await mcp_query(client,sql,purpose)
        return await investigate(question,reader)

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('question',nargs='?',default='Compare late delivery rate and review scores from May 2018 to June 2018')
    args=p.parse_args()
    try: output=asyncio.run(run(args.question))
    except Exception as e:
        while isinstance(e,BaseExceptionGroup) and e.exceptions:e=e.exceptions[0]
        print(json.dumps({'status':'MULTIDOMAIN_NOT_VALIDATED','error_type':type(e).__name__,
            'reason':str(e)[:600], 'next_gate':'Inspect MCP source permissions, cohort alignment and intended contract; do not bypass validation'},indent=2))
        return 1
    print(json.dumps(output,indent=2,ensure_ascii=False))
    return 0
if __name__=='__main__':sys.exit(main())
