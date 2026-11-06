"""Execute financial eligibility checks through the existing read-only MCP interface."""
import argparse
import asyncio
import json
from pathlib import Path
from agent.phase4b53_eligibility import Period, queries, assess, summarize

ROOT=Path(__file__).resolve().parents[1]

def unwrap(raw):
    if not isinstance(raw,dict) or raw.get('ok') is False:raise ValueError('MCP_ERROR:'+str(raw)[:200])
    data=raw.get('data',raw)
    rows=data.get('rows') if isinstance(data,dict) else None
    if not isinstance(rows,list) or len(rows)!=1 or not isinstance(rows[0],dict):raise ValueError('EXPECTED_ONE_RESULT_ROW')
    return rows[0]

async def main(periods,dry):
    if dry:
        for p in periods:
            print('PERIOD',p.start,p.end)
            for name,query in queries(p).items():print(name,query)
        print('DRY RUN: no database access');return
    from mcp import Client
    from mcp_server.server import mcp
    from agent.phase4b1_semantic_playground import call
    results=[]
    async with Client(mcp) as client:
        for p in periods:
            data={};error=None
            for name,query in queries(p).items():
                try:
                    raw=await call(client,'run_readonly_sql',{'query':query,'purpose':'Verify observed financial eligibility (read only)',
                         'expected_grain':'one aggregate row','max_rows':1,'timeout_ms':20000})
                    data[name]=unwrap(raw)
                except Exception as exc:
                    while isinstance(exc,BaseExceptionGroup) and exc.exceptions:exc=exc.exceptions[0]
                    error=f'{name}: {type(exc).__name__}: {str(exc)[:250]}'
                    break
            item=assess(p,data) if error is None else {'period':[p.start,p.end],'status':'INCONCLUSIVE','issues':[error],'execution_approved':False}
            results.append(item)
            print(p.start,p.end,item['status'])
            for c in item.get('checks',[]):
                if not c['passed']:print('  FAILED',c['name'],c['detail'])
            for issue in item.get('issues',[]):print('  ERROR',issue)
    report=summarize(results)
    target=ROOT/'reports'/'phase4b53_financial_eligibility.json'
    target.parent.mkdir(parents=True,exist_ok=True)
    target.write_text(json.dumps(report,indent=2),encoding='utf-8')
    print('OVERALL',report['status'],'APPROVAL',report['execution_approved'])
    print('SAVED',target)

if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('--dry-run',action='store_true')
    parser.add_argument('--period',nargs=2,action='append',metavar=('START','END'))
    args=parser.parse_args()
    periods=[Period(*x) for x in (args.period or [('2017-11-01','2017-12-01'),('2018-03-01','2018-04-01'),('2018-06-01','2018-07-01')])]
    asyncio.run(main(periods,args.dry_run))
