"""Compare independent June PostgreSQL totals with live MCP execution."""
import json,sys
from decimal import Decimal

def compare(mcp,pg):
    if mcp.get('status')!='LIVE_MCP_VALIDATED' or mcp.get('period')!=pg.get('period') or mcp['period']!=['2018-06-01','2018-07-01']:raise ValueError('Unverified source or wrong June period')
    for k,v in pg['population'].items():
        if type(v) is not int or mcp['population'].get(k)!=v:raise ValueError('Population mismatch '+k)
    for k in ('late_delivery_rate','average_delivery_days','delivered_order_count','delivery_evidence_coverage'):
        p=pg['metrics'][k];m=mcp['metrics'][k]['value']
        if p is None or abs(Decimal(str(p))-Decimal(m))>Decimal('0.00001'):raise ValueError('Metric mismatch '+k)
    if mcp.get('causal_claim') is not False:raise ValueError('Causal claim')
    return {'status':'MCP_POSTGRES_RECONCILED','metric_count':4,'period':mcp['period'],'causal_claim':False}
if __name__=='__main__':
    try:
        with open(sys.argv[1],encoding='utf-8-sig') as f:a=json.load(f)
        with open(sys.argv[2],encoding='utf-8-sig') as f:b=json.load(f)
        print(json.dumps(compare(a,b),indent=2))
    except Exception as exc:print(json.dumps({'status':'RECONCILIATION_FAILED','reason':str(exc)},indent=2));sys.exit(1)
