"""Read-only MCP verification; never promotes to execution approval."""
import argparse,asyncio,json
from pathlib import Path
from agent.phase4b51_metric_contracts import ROOT,CHECKS,query,assess,proposed_catalog

async def run(args):
    audit=json.loads((ROOT/'reports/phase4b42_relationship_audit.json').read_text(encoding='utf-8'))
    catalog=json.loads((ROOT/'config/metric_catalog.json').read_text(encoding='utf-8'))
    proposed=proposed_catalog(catalog)
    target=ROOT/'reports/phase4b51_proposed_metric_catalog.json'
    target.parent.mkdir(parents=True,exist_ok=True)
    target.write_text(json.dumps(proposed,indent=2),encoding='utf-8')
    if args.dry_run:
        for name in CHECKS:print(name, query(name,args.start,args.end))
        print('DRY RUN: No database access or contract approval.');return
    from mcp import Client
    from mcp_server.server import mcp
    from agent.phase4b1_semantic_playground import call
    results=[]
    async with Client(mcp) as client:
        for name in CHECKS:
            try:
                raw=await call(client,'run_readonly_sql',{'query':query(name,args.start,args.end),
                   'purpose':'Metric definition verification only, read-only',
                   'expected_grain':'single period-level aggregate','max_rows':1,'timeout_ms':20000})
                rows=raw.get('rows',[]) if isinstance(raw,dict) else []
                if len(rows)!=1:raise ValueError('Expected exactly one row; got '+str(len(rows)))
                result=assess(name,rows[0],audit=audit)
            except Exception as exc:
                cause=exc
                while isinstance(cause,BaseExceptionGroup) and cause.exceptions:cause=cause.exceptions[0]
                result={'metric':name,'assessment':'ERROR','issues':[type(cause).__name__+': '+str(cause)[:250]],'execution_approved':False}
            results.append(result)
            print(name,result['assessment'],'rows',result.get('eligible_source_rows'),'value',result.get('metric_value'),'issues',result['issues'])
    out=ROOT/'reports/phase4b51_metric_live_verification.json'
    out.write_text(json.dumps({'phase':'4b5.1','period':{'start':args.start,'end_exclusive':args.end},'results':results,
                               'disclaimer':'Not a business reconciliation and no execution approval'},indent=2,default=str),encoding='utf-8')
    print('Saved:',out)

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--start',default='2018-06-01');p.add_argument('--end',default='2018-07-01');p.add_argument('--dry-run',action='store_true');args=p.parse_args()
    try:asyncio.run(run(args))
    except Exception as e:
        while isinstance(e,BaseExceptionGroup) and e.exceptions:e=e.exceptions[0]
        print('FAILED:',type(e).__name__,str(e)[:500]);raise SystemExit(1)
