"""CX-aware unified playground; existing finance and graph dispatcher preserved."""
import asyncio,json
from pathlib import Path
from agent.phase4c17_delivery_compare import DeliveryComparisonSession
from agent.phase4c8_unified_dispatch import dispatch as prior_dispatch
from agent.phase4c6_nl_investigation import GeminiInvestigationInterpreter
from agent.phase4c2_graph_routing import UnifiedContext
from agent.phase4c1_router import GeminiRouter
from agent.phase4b57_nl_dynamic_finance import Interpreter,mcp_query
from agent.phase4b44_gemini_interpreter import GeminiSemanticInterpreter
from agent.phase4b43_graph_planner import GraphPlanner

async def main():
    session=DeliveryComparisonSession(UnifiedContext())
    router=GeminiRouter();finance=Interpreter();graph=GeminiSemanticInterpreter()
    investigation=GeminiInvestigationInterpreter()
    planner=GraphPlanner(Path(__file__).resolve().parents[1]/'reports/phase4b42_relationship_audit.json')
    from mcp import Client
    from mcp_server.server import mcp
    from agent.phase4b1_semantic_playground import call
    async with Client(mcp) as client:
        async def finance_reader(sql,purpose):return await mcp_query(client,sql,purpose)
        async def graph_reader(sql,request,plan):
            return await call(client,'run_readonly_sql',{
                'query':sql,'purpose':'Governed semantic graph analysis',
                'expected_grain':'grouped by '+','.join(request.dimensions) if request.dimensions else 'one aggregate',
                'max_rows':request.limit,'timeout_ms':20000})
        print('OpsLens 4C.17 - finance + graph + investigation + customer satisfaction + delivery; exit to quit')
        while True:
            try:question=input('\nOpsLens > ').strip()
            except (EOFError,KeyboardInterrupt):break
            if question.lower() in ('exit','quit'):break
            if not question:continue
            try:
                result=await session.dispatch(question,prior_dispatch,router,finance,finance_reader,graph,planner,graph_reader,investigation)
                print(json.dumps(result,indent=2,default=str))
            except Exception as exc:
                while isinstance(exc,BaseExceptionGroup) and exc.exceptions:exc=exc.exceptions[0]
                print('BLOCKED:',type(exc).__name__,str(exc)[:450])
                print('Previously successful contexts unchanged.')
if __name__=='__main__':asyncio.run(main())
