"""Compare MCP product results with independent raw-table PostgreSQL June reconciliation."""
import json
import sys
from decimal import Decimal, InvalidOperation
from pathlib import Path

EXPECTED_PERIOD=['2018-06-01','2018-07-01']
EXPECTED_CATEGORY='beleza_saude'
COUNTS=('total_units','unique_items','total_orders','invalid_items','category_units','category_unique_items','category_orders','category_invalid_items')

def _read(path):
    text=Path(path).read_text(encoding='utf-8-sig').strip()
    value=json.loads(text)
    if not isinstance(value,dict):raise ValueError('JSON must contain one object')
    return value

def _decimal(v):
    if isinstance(v,bool) or v is None:raise ValueError('Invalid numeric')
    try:d=Decimal(str(v))
    except InvalidOperation as e:raise ValueError('Invalid numeric') from e
    if not d.is_finite():raise ValueError('Nonfinite numeric')
    return d

def _integer(v):
    if isinstance(v,bool) or v is None:raise ValueError('Invalid count')
    d=_decimal(v)
    if d!=d.to_integral_value() or d<0:raise ValueError('Invalid count')
    return int(d)

def compare(mcp,pg):
    if mcp.get('status')!='LIVE_MCP_VALIDATED':raise ValueError('MCP output not validated')
    if mcp.get('period')!=EXPECTED_PERIOD or mcp.get('category')!=EXPECTED_CATEGORY:raise ValueError('Wrong reference cohort')
    if mcp.get('source')!='semantic.order_item_product_evidence_v1':raise ValueError('Unexpected source')
    if mcp.get('causal_claim') is not False or mcp.get('inventory_claim_allowed') is not False:raise ValueError('Unsupported claim')
    population=mcp['population']
    for field in COUNTS:
        if _integer(population[field])!=_integer(pg[field]):raise ValueError(f'Mismatch: {field}')
    if _integer(pg['unique_items'])!=_integer(pg['total_units']) or _integer(pg['category_unique_items'])!=_integer(pg['category_units']):raise ValueError('Duplicate item grain')
    if _integer(pg['invalid_items']) or _integer(pg['category_invalid_items']):raise ValueError('Invalid source values')
    for key in ('total_gmv','category_gmv'):
        actual_key={'total_gmv':'total_item_gmv','category_gmv':'category_item_gmv'}[key]
        if abs(_decimal(mcp[actual_key])-_decimal(pg[key]))>Decimal('0.00001'):raise ValueError(f'Mismatch: {key}')
    units=_integer(pg['category_units']); total=_decimal(pg['total_gmv']); selected=_decimal(pg['category_gmv'])
    if not units or total<=0:raise ValueError('Reference category has insufficient denominator')
    expected={'category_order_count':(Decimal(_integer(pg['category_orders'])),'orders'),
       'units_sold':(Decimal(units),'units'), 'item_gmv':(selected,'money'),
       'average_item_price':(selected/units,'money_per_unit'),
       'category_gmv_share':(selected/total*100,'percent')}
    if set(mcp['metrics'])!=set(expected):raise ValueError('Missing or extra metric')
    for k,(target,unit) in expected.items():
        record=mcp['metrics'][k]
        if record['unit']!=unit:raise ValueError(f'Wrong unit: {k}')
        if abs(_decimal(record['value'])-target)>Decimal('0.000001'):raise ValueError(f'Mismatch: {k}')
    return {'status':'MCP_POSTGRES_RECONCILED','metric_count':len(expected),'period':EXPECTED_PERIOD,'category':EXPECTED_CATEGORY,'causal_claim':False,'inventory_claim_allowed':False}

def main():
    try:
        if len(sys.argv)!=3:raise ValueError('Usage: python -m scripts.phase4c19b_compare MCP.json PG.json')
        result=compare(_read(sys.argv[1]),_read(sys.argv[2]))
    except Exception as exc:
        print(json.dumps({'status':'RECONCILIATION_FAILED','reason':str(exc)[:500]},indent=2));return 1
    print(json.dumps(result,indent=2));return 0
if __name__=='__main__':sys.exit(main())

