"""Opt-in governed semantic bridge. No modifications to earlier agent entrypoints."""
import argparse, asyncio, json
from pathlib import Path
from agent.phase4b55_semantic_bridge import SemanticQuery, compile_query, finance_evidence, finance_comparison

async def execute(compiled):
    if compiled['route'] != 'governed_finance':
        raise ValueError('CLI only executes finance route; graph routing is compiler-tested separately')
    from mcp import Client
    from mcp_server.server import mcp
    from agent.phase4b1_semantic_playground import call
    plan=compiled['plan']
    async with Client(mcp) as client:
        response=await call(client,'run_readonly_sql',{
            'query':plan['sql'], 'purpose':'4B.5.5 governed finance evidence',
            'expected_grain':'one aggregate row', 'max_rows':1})
    return finance_evidence(compiled,response)

async def main():
    parser=argparse.ArgumentParser(description='Finance to semantic bridge (explicit governed IDs)')
    parser.add_argument('--metric',required=True)
    parser.add_argument('--start',required=True);parser.add_argument('--end',required=True)
    parser.add_argument('--compare-start');parser.add_argument('--compare-end')
    parser.add_argument('--dry-run',action='store_true')
    args=parser.parse_args()
    if bool(args.compare_start)!=bool(args.compare_end): parser.error('comparison requires two boundaries')
    root=Path(__file__).resolve().parents[1]
    report=json.loads((root/'reports/phase4b53_financial_eligibility.json').read_text(encoding='utf-8'))
    plans=[compile_query(SemanticQuery(args.metric,args.start,args.end),reconciliation=report)]
    if args.compare_start:
        plans.append(compile_query(SemanticQuery(args.metric,args.compare_start,args.compare_end),reconciliation=report))
    for p in plans:
        print('BRIDGE PLAN:',json.dumps({k:v for k,v in p.items() if k!='plan'},indent=2))
        print('GOVERNED SQL:',p['plan']['sql'])
    if args.dry_run: print('DRY RUN: no SQL executed');return
    results=[await execute(p) for p in plans]
    for evidence in results: print('EVIDENCE:',json.dumps(evidence,indent=2))
    if len(results)==2: print('COMPARISON:',json.dumps(finance_comparison(*results),indent=2))
    print('No causal inference, joins, or dimensional finance permission granted.')

if __name__=='__main__':
    try:asyncio.run(main())
    except Exception as e:
        node=e
        while isinstance(node,BaseExceptionGroup) and node.exceptions:node=node.exceptions[0]
        print('BLOCKED:',type(node).__name__,str(node)[:500]);raise SystemExit(1)
