"""CLI for tightly scoped governed financial measurement/period comparisons."""
import argparse, asyncio, json
from pathlib import Path
from agent.phase4b54_governed_finance import Period,sql_for,validate_measurement,compare,FinanceGateError

async def execute(plan):
    from mcp import Client
    from mcp_server.server import mcp
    from agent.phase4b1_semantic_playground import call
    async with Client(mcp) as client:
        response=await call(client,'run_readonly_sql',{
            'query':plan['sql'],'purpose':'Reconciled finance-only semantic measurement',
            'expected_grain':'one aggregate row','max_rows':1})
    return validate_measurement(plan,response)

async def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--metric',required=True)
    parser.add_argument('--start',required=True);parser.add_argument('--end',required=True)
    parser.add_argument('--compare-start');parser.add_argument('--compare-end')
    parser.add_argument('--dry-run',action='store_true')
    a=parser.parse_args()
    if bool(a.compare_start)!=bool(a.compare_end):raise FinanceGateError('Comparison needs both dates')
    root=Path(__file__).resolve().parents[1]
    report=json.loads((root/'reports/phase4b53_financial_eligibility.json').read_text(encoding='utf-8'))
    plans=[sql_for(a.metric,Period(a.start,a.end),report)]
    if a.compare_start:
        plans.append(sql_for(a.metric,Period(a.compare_start,a.compare_end),report))
    for p in plans:
        print('GATED PLAN:',json.dumps({k:v for k,v in p.items() if k!='sql'},indent=2))
        print('SQL:',p['sql'])
    if a.dry_run: print('DRY RUN: no database access');return
    measurements=[]
    for plan in plans:
        measured=await execute(plan);measurements.append(measured)
        print('MEASUREMENT:',json.dumps(measured,indent=2))
    if len(measurements)==2:print('COMPARISON:',json.dumps(compare(*measurements),indent=2))
    print('No metric joins, dimensions, financial certification or causal conclusions authorized.')
if __name__=='__main__':
    try:asyncio.run(main())
    except Exception as e:
        node=e
        while isinstance(node,BaseExceptionGroup) and node.exceptions:node=node.exceptions[0]
        print('BLOCKED:',type(node).__name__,str(node)[:500]);raise SystemExit(1)
