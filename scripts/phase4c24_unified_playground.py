"""Opt-in CLI using the existing 4C20 session and a language pre-router."""
import asyncio, json
from pathlib import Path
from agent.phase4c24_language import LanguageSession
from agent.phase4c20_product_nlp import ProductNLPSession
from agent.phase4c17_delivery_compare import DeliveryComparisonSession
from agent.phase4c8_unified_dispatch import dispatch as prior_dispatch
from agent.phase4c6_nl_investigation import GeminiInvestigationInterpreter
from agent.phase4c2_graph_routing import UnifiedContext
from agent.phase4c1_router import GeminiRouter
from agent.phase4b57_nl_dynamic_finance import Interpreter,mcp_query
from agent.phase4b44_gemini_interpreter import GeminiSemanticInterpreter
from agent.phase4b43_graph_planner import GraphPlanner

async def main():
    session=LanguageSession(ProductNLPSession(DeliveryComparisonSession(UnifiedContext())))
    router=GeminiRouter();finance=Interpreter();graph=GeminiSemanticInterpreter()
    investigation=GeminiInvestigationInterpreter()
    planner=GraphPlanner(Path(__file__).resolve().parents[1]/'reports/phase4b42_relationship_audit.json')
    from mcp import Client
    from mcp_server.server import mcp
    from agent.phase4b1_semantic_playground import call
    async with Client(mcp) as client:
        async def finance_reader(sql,purpose):return await mcp_query(client,sql,purpose)
        async def graph_reader(sql,request,plan):
            return await call(client,'run_readonly_sql',{'query':sql,'purpose':'Governed semantic graph analysis',
                'expected_grain':'grouped by '+','.join(request.dimensions) if request.dimensions else 'one aggregate',
                'max_rows':request.limit,'timeout_ms':20000})
        print('OpsLens 4C.24 - conservative language recovery; exit to quit')
        while True:
            try:q=input('\nOpsLens > ').strip()
            except (EOFError,KeyboardInterrupt):break
            if q.lower() in ('exit','quit'):break
            if not q:continue
            try:
                r=await session.dispatch(q,prior_dispatch,router,finance,finance_reader,graph,planner,graph_reader,investigation)
                print(json.dumps(r,indent=2,default=str,ensure_ascii=False))
            except Exception as exc:
                while isinstance(exc,BaseExceptionGroup) and exc.exceptions:exc=exc.exceptions[0]
                print('BLOCKED:',type(exc).__name__,str(exc)[:450])
if __name__=='__main__':asyncio.run(main())
