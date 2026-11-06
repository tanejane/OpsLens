"""Live routing demonstration. Finance queries use existing vetted MCP path."""
import asyncio,json
from agent.phase4c1_router import Conversation,GeminiRouter,route_and_execute
from agent.phase4b57_nl_dynamic_finance import Interpreter,mcp_query

async def main():
    router=GeminiRouter();finance=Interpreter();context=Conversation()
    from mcp import Client
    from mcp_server.server import mcp
    print('OpsLens Phase 4C.1 — capability router. Exit with exit.')
    async with Client(mcp) as client:
        async def reader(sql,purpose):return await mcp_query(client,sql,purpose)
        while True:
            try:q=input('\nOpsLens > ').strip()
            except (KeyboardInterrupt,EOFError):break
            if q.lower() in ('exit','quit'):break
            if not q:continue
            try:
                output,next_context=await route_and_execute(q,context,router,finance,reader)
                print(json.dumps(output,indent=2,default=str));context=next_context
            except Exception as ex:
                while isinstance(ex,BaseExceptionGroup) and ex.exceptions:ex=ex.exceptions[0]
                print('BLOCKED:',type(ex).__name__,str(ex)[:300]);print('Previous successful context unchanged.')
if __name__=='__main__':asyncio.run(main())
