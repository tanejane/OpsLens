"""Interactive natural-language semantic grounding + graph compiler + MCP."""
import asyncio,json
from pathlib import Path
from agent.phase4b44_context_grounding import ground
from agent.phase4b44_gemini_interpreter import GeminiSemanticInterpreter
from agent.phase4b43_graph_planner import GraphPlanner,PlanningRejected

async def run():
    root=Path(__file__).resolve().parents[1]
    planner=GraphPlanner(root/'reports/phase4b42_relationship_audit.json')
    gemini=GeminiSemanticInterpreter()
    previous=None
    print('OpsLens 4B.4.4 — semantic grounding playground | exit to quit')
    while True:
        question=input('\nOpsLens > ').strip()
        if not question or question.lower() in ('exit','quit'):break
        try:
            interpretation=gemini.interpret(question,planner.map,previous)
            result=ground(interpretation,planner.map,previous)
            print('INTERPRETATION:',interpretation.model_dump_json(indent=2))
            print('GROUNDING:',result.status,result.message)
            if result.status!='READY':continue
            plan=planner.compile(result.request)
            print('SEMANTIC PLAN:',json.dumps({k:v for k,v in plan.items() if k!='sql'},indent=2))
            print('GOVERNED SQL:',plan['sql'])
            from mcp import Client
            from mcp_server.server import mcp
            from agent.phase4b1_semantic_playground import call
            async with Client(mcp) as client:
                rows=await call(client,'run_readonly_sql',{
                    'query':plan['sql'],'purpose':'Natural-language semantic map analysis',
                    'expected_grain':'grouped by '+','.join(plan['dimensions']) if plan['dimensions'] else 'single metric row',
                    'max_rows':result.request.limit})
            print('MCP RESULT:',json.dumps(rows,indent=2,default=str))
            if not isinstance(rows,dict) or not rows.get('rows'):
                print('NO EVIDENCE: empty result; do not infer zero or a business conclusion.')
            else:
                previous=result.request
                print('LIMITATION: descriptive result; no causal attribution. Context saved for next question.')
        except Exception as exc:
            node=exc
            while isinstance(node,BaseExceptionGroup) and node.exceptions:node=node.exceptions[0]
            print('BLOCKED/FAILED:',type(node).__name__,str(node)[:500])
if __name__=='__main__':asyncio.run(run())
