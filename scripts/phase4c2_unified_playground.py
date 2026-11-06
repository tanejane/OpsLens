"""OpsLens Phase 4C.2 unified finance + graph routing, read-only MCP."""
import asyncio,json
from pathlib import Path
from agent.phase4c2_graph_routing import UnifiedContext,dispatch
from agent.phase4c1_router import GeminiRouter
from agent.phase4b57_nl_dynamic_finance import Interpreter,mcp_query
from agent.phase4b44_gemini_interpreter import GeminiSemanticInterpreter
from agent.phase4b43_graph_planner import GraphPlanner

async def main():
    state=UnifiedContext();router=GeminiRouter();finance=Interpreter()
    graph=GeminiSemanticInterpreter()
    root=Path(__file__).resolve().parents[1]
    planner=GraphPlanner(root/'reports/phase4b42_relationship_audit.json')
    from mcp import Client
    from mcp_server.server import mcp
    from agent.phase4b1_semantic_playground import call
    print('OpsLens 4C.2 — unified finance + graph analytics; type exit to quit')
    async with Client(mcp) as client:
        async def finance_reader(sql,purpose):return await mcp_query(client,sql,purpose)
        async def graph_reader(sql,request,plan):
            return await call(client,'run_readonly_sql',{
                'query':sql,'purpose':'Governed semantic graph analysis',
                'expected_grain':'grouped by '+','.join(request.dimensions) if request.dimensions else 'one aggregate',
                'max_rows':request.limit,'timeout_ms':20000})
        while True:
            try:question=input('\nOpsLens > ').strip()
            except (EOFError,KeyboardInterrupt):break
            if question.lower() in ('exit','quit'):break
            if not question:continue
            try:
                result,next_state=await dispatch(question,state,router,finance,finance_reader,
                                                 graph,planner,graph_reader)
                print(json.dumps(result,indent=2,default=str))
                state=next_state
            except Exception as exc:
                while isinstance(exc,BaseExceptionGroup) and exc.exceptions:exc=exc.exceptions[0]
                print('BLOCKED:',type(exc).__name__,str(exc)[:400])
                print('Previous successful context unchanged.')
if __name__=='__main__':asyncio.run(main())
