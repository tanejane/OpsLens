"""Compare live MCP output against separately run direct PostgreSQL audit JSON."""
import argparse
from decimal import Decimal, InvalidOperation
import json
import sys

FIELDS={'average_review_score':'average_review_score','low_rating_rate':'low_rating_rate','review_coverage':'review_coverage','reviewed_order_count':'reviewed_orders'}
POP=('eligible_orders','reviewed_orders','low_rating_orders','multi_review_orders')

def compare(mcp,audit):
    if mcp.get('status')!='LIVE_MCP_VALIDATED': raise ValueError('MCP not validated')
    if not isinstance(audit,dict):raise ValueError('Invalid PostgreSQL audit')
    if int(audit['eligible_orders']) != int(audit['distinct_orders']):raise ValueError('Direct audit has duplicate order grain')
    for key in POP:
        if int(mcp['population'][key]) != int(audit[key]):raise ValueError('Population mismatch: '+key)
    for metric,field in FIELDS.items():
        a=Decimal(str(audit[field]));b=Decimal(str(mcp['metrics'][metric]['value']))
        if not (a.is_finite() and b.is_finite()) or abs(a-b)>Decimal('0.00001'):
            raise ValueError('Metric mismatch: '+metric)
    return {'status':'MCP_POSTGRES_RECONCILED','metric_count':4,'period':mcp['period'],'causal_claim':False}

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('mcp_json');p.add_argument('audit_json')
    x=p.parse_args()
    try:
        with open(x.mcp_json,encoding='utf-8-sig') as f: mcp=json.load(f)
        with open(x.audit_json,encoding='utf-8-sig') as f: audit=json.load(f)
        if mcp.get('period')!=['2018-06-01','2018-07-01']:raise ValueError('Independent SQL audit is fixed to June 2018')
        print(json.dumps(compare(mcp,audit),indent=2));return 0
    except (OSError,ValueError,KeyError,TypeError,InvalidOperation) as e:
        print(json.dumps({'status':'RECONCILIATION_FAILED','reason':str(e)},indent=2));return 1
if __name__=='__main__':sys.exit(main())
