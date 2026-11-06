"""Execute a semantic-map-compiled request via the existing read-only MCP server.
No model generated SQL and no automatic write permissions.
"""
import argparse,asyncio,json
from pathlib import Path
from agent.phase4b43_graph_planner import GraphPlanner,AnalysisRequest,PlanningRejected

async def main(args):
    project=Path(__file__).resolve().parents[1]
    plan=GraphPlanner(project/'reports'/'phase4b42_relationship_audit.json').compile(
       AnalysisRequest(args.metric,tuple(args.dimension or []),args.start,args.end,args.order,args.limit))
    print('PLAN:',json.dumps({k:v for k,v in plan.items() if k!='sql'},indent=2))
    print('GOVERNED SQL:',plan['sql'])
    if args.dry_run:
        print('DRY RUN: No live query executed');return
    from mcp import Client
    from mcp_server.server import mcp
    from agent.phase4b1_semantic_playground import call
    async with Client(mcp) as client:
        result=await call(client,'run_readonly_sql',{
            'query':plan['sql'],'purpose':'Semantic graph governed analysis',
            'expected_grain':('grouped by '+','.join(plan['dimensions'])) if plan['dimensions'] else 'one aggregate row',
            'max_rows':args.limit})
    print('MCP RESULTS:',json.dumps(result,indent=2,default=str))
    rows=result.get('rows',[]) if isinstance(result,dict) else []
    if not rows:print('NO DATA: Empty results do not imply metric value zero; inspect source period and filters.')
    print('LIMITATION: Descriptive result only. No causal or root-cause reasoning has been performed.')

if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('--metric',required=True)
    parser.add_argument('--dimension',action='append')
    parser.add_argument('--start',required=True)
    parser.add_argument('--end',required=True,help='exclusive end date YYYY-MM-DD')
    parser.add_argument('--order',choices=['asc','desc'],default='desc')
    parser.add_argument('--limit',type=int,default=10)
    parser.add_argument('--dry-run',action='store_true')
    args=parser.parse_args()
    try:asyncio.run(main(args))
    except Exception as e:
        node=e
        while isinstance(node,BaseExceptionGroup) and node.exceptions:node=node.exceptions[0]
        print('BLOCKED/FAILED:',type(node).__name__,str(node)[:500]);raise SystemExit(1)
