"""CLI: live four-query period reconciliation, then gated metric measurement via MCP."""
import argparse, asyncio, json
from agent.phase4b56_dynamic_period import requested_period, audit_queries, audit_token, compile_metric, measurement_evidence


def unwrap(response):
    if not isinstance(response,dict) or response.get('ok') is False:
        raise ValueError('MCP read-only query failed: '+str(response)[:200])
    data=response.get('data',response)
    rows=data.get('rows') if isinstance(data,dict) else None
    if not isinstance(rows,list) or len(rows)!=1 or not isinstance(rows[0],dict):
        raise ValueError('Expected one aggregate result row')
    return rows[0]


async def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('--metric',required=True)
    ap.add_argument('--start',required=True)
    ap.add_argument('--end',required=True)
    ap.add_argument('--dry-run',action='store_true')
    args=ap.parse_args()
    p=requested_period(args.start,args.end)
    qs=audit_queries(p)
    if args.dry_run:
        for name,sql in qs.items(): print('AUDIT',name,sql)
        print('DRY RUN: metric SQL generated only after a successful live audit; no SQL executed.')
        return
    from mcp import Client
    from mcp_server.server import mcp
    from agent.phase4b1_semantic_playground import call
    async with Client(mcp) as client:
        raw={}
        for name,sql in qs.items():
            response=await call(client,'run_readonly_sql',{
                'query':sql,'purpose':'4B.5.6 on-demand finance period reconciliation',
                'expected_grain':'one aggregate row','max_rows':1,'timeout_ms':20000})
            raw[name]=unwrap(response)
        token=audit_token(p,raw)
        print('PERIOD',token['status'],token['period'])
        plan=compile_metric(args.metric,p,token)
        result=await call(client,'run_readonly_sql',{
            'query':plan['sql'],'purpose':'4B.5.6 governed finance metric total',
            'expected_grain':'one aggregate row','max_rows':1,'timeout_ms':20000})
        evidence=measurement_evidence(plan,unwrap_metric(result),token)
    print('EVIDENCE',json.dumps(evidence,indent=2))
    print('No persistent permissions, dimensional joins, or causal conclusions granted.')


def unwrap_metric(raw):
    if not isinstance(raw,dict) or raw.get('ok') is False: raise ValueError('MCP metric query failed')
    return raw.get('data',raw)

if __name__=='__main__':
    try: asyncio.run(main())
    except Exception as exc:
        while isinstance(exc,BaseExceptionGroup) and exc.exceptions: exc=exc.exceptions[0]
        print('BLOCKED',type(exc).__name__,str(exc)[:500]);raise SystemExit(1)
