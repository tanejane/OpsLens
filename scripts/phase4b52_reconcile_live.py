"""Run bounded multi-month reconciliation through the existing MCP boundary."""
import argparse, asyncio, json
from pathlib import Path
from agent.phase4b52_reconciliation import Period, queries, result_for, summary

ROOT=Path(__file__).resolve().parents[1]

def unwrap(raw):
    if not isinstance(raw,dict):raise ValueError('MCP_NON_OBJECT_RESPONSE')
    if raw.get('ok') is False:raise ValueError('MCP_ERROR:'+str(raw.get('error'))[:300])
    data=raw.get('data',raw)
    if not isinstance(data,dict):raise ValueError('MCP_DATA_NOT_OBJECT')
    rows=data.get('rows',[])
    if not isinstance(rows,list) or len(rows)!=1 or not isinstance(rows[0],dict):
        raise ValueError('EXPECTED_EXACTLY_ONE_ROW')
    return rows[0]

async def run(periods, dry):
    if dry:
        for p in periods:
            print('PERIOD:',p.start,p.end)
            for name,sql in queries(p).items():print(name,sql)
        print('DRY RUN; no database query.');return
    from mcp import Client
    from mcp_server.server import mcp
    from agent.phase4b1_semantic_playground import call
    out=[]
    async with Client(mcp) as client:
        for p in periods:
            vals={};error=None
            for name,sql in queries(p).items():
                try:
                    raw=await call(client,'run_readonly_sql',{'query':sql,'purpose':'Read-only semantic financial reconciliation',
                        'expected_grain':'one row, single period','max_rows':1,'timeout_ms':20000})
                    vals[name]=unwrap(raw)
                except Exception as exc:
                    while isinstance(exc,BaseExceptionGroup) and exc.exceptions:exc=exc.exceptions[0]
                    error=f'{name}: {type(exc).__name__}: {str(exc)[:260]}'
                    break
            item=result_for(p,vals) if error is None else {'period':{'start':p.start,'end_exclusive':p.end},'status':'INCONCLUSIVE','issues':[error],'execution_approved':False}
            out.append(item)
            print(p.start,p.end,item['status'])
            for ch in item.get('checks',[]):
                if not ch['passed']:print('  CHECK FAILED:',ch['check'],ch['detail'])
            for issue in item.get('issues',[]):print('  ERROR:',issue)
    report=summary(out)
    target=ROOT/'reports/phase4b52_reconciliation.json';target.parent.mkdir(parents=True,exist_ok=True)
    target.write_text(json.dumps(report,indent=2),encoding='utf-8')
    print('OVERALL:',report['status'],'| approval:',report['execution_approved'])
    print('SAVED:',target)

if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('--dry-run',action='store_true')
    ap.add_argument('--period',action='append',nargs=2,metavar=('START','END'),help='Half-open date window; repeat for multiple periods')
    args=ap.parse_args()
    periods=[Period(*v) for v in (args.period or [('2017-11-01','2017-12-01'),('2018-03-01','2018-04-01'),('2018-06-01','2018-07-01')])]
    try:asyncio.run(run(periods,args.dry_run))
    except Exception as exc:
        while isinstance(exc,BaseExceptionGroup) and exc.exceptions:exc=exc.exceptions[0]
        print('FAILED:',type(exc).__name__,str(exc)[:400]);raise SystemExit(1)
