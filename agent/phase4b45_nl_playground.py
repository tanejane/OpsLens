"""Phase 4B.4.5: natural-language graph playground with coverage and result safeguards."""
import asyncio, json
from pathlib import Path
from agent.phase4b44_context_grounding import ground
from agent.phase4b44_gemini_interpreter import GeminiSemanticInterpreter
from agent.phase4b43_graph_planner import GraphPlanner
from agent.phase4b45_result_validation import coverage_probe, assess_result

async def run():
    root=Path(__file__).resolve().parents[1]
    planner=GraphPlanner(root/'reports'/'phase4b42_relationship_audit.json')
    gemini=GeminiSemanticInterpreter()
    previous=None
    print('OpsLens 4B.4.5 — governed semantic evidence playground | exit to quit')
    while True:
        question=input('\nOpsLens > ').strip()
        if not question or question.lower() in ('exit','quit'): break
        try:
            interpretation=gemini.interpret(question,planner.map,previous)
            grounded=ground(interpretation,planner.map,previous)
            print('INTERPRETATION:',interpretation.model_dump_json(indent=2))
            print('GROUNDING:',grounded.status,grounded.message)
            if grounded.status!='READY': continue
            req=grounded.request
            plan=planner.compile(req)
            probe_sql=coverage_probe(plan,req,planner.map)
            print('PLAN:',json.dumps({k:v for k,v in plan.items() if k!='sql'},indent=2))
            print('GOVERNED SQL:',plan['sql'])
            from mcp import Client
            from mcp_server.server import mcp
            from agent.phase4b1_semantic_playground import call
            async with Client(mcp) as client:
                probe=await call(client,'run_readonly_sql',{
                    'query':probe_sql,'purpose':'Validate metric source date-range availability',
                    'expected_grain':'one source coverage row','max_rows':1})
                # Do not run an expensive metric query if coverage itself is absent or invalid.
                from agent.phase4b45_result_validation import _count
                n=_count(probe)
                if n is None or n==0:
                    assessment=assess_result(req,plan,probe,{'rows':[]})
                    print('ASSESSMENT:',json.dumps(assessment.__dict__,indent=2));continue
                result=await call(client,'run_readonly_sql',{
                    'query':plan['sql'],'purpose':'Governed metric analysis with coverage check',
                    'expected_grain':('grouped by '+','.join(plan['dimensions'])) if plan['dimensions'] else 'one aggregate row',
                    'max_rows':req.limit})
            assessment=assess_result(req,plan,probe,result)
            print('MCP RESULT:',json.dumps(result,indent=2,default=str))
            print('ASSESSMENT:',json.dumps(assessment.__dict__,indent=2))
            if assessment.can_save_context: previous=req
        except Exception as exc:
            node=exc
            while isinstance(node,BaseExceptionGroup) and node.exceptions: node=node.exceptions[0]
            print('BLOCKED/FAILED:',type(node).__name__,str(node)[:500])
if __name__=='__main__': asyncio.run(run())
