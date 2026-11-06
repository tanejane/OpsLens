"""Assess grounded, read-only product/category relationship evidence. No grants."""
import json
import sys
from decimal import Decimal, InvalidOperation
from pathlib import Path


def assess(data):
    failures=[]
    warnings=[]
    try:
        if data['audit_version'] != '4C18_V1' or data['sources'] != {'orders':'commerce.orders','items':'commerce.order_items','products':'catalog.products'}:
            raise ValueError('unexpected source contract')
        if any(data.get(x) is not expected for x,expected in [('audit_only',True),('approved_for_mcp',False),('inventory_evidence_available',False),('causal_claim',False)]):
            raise ValueError('unsafe authorization or provenance flag')
        a,b,c,r = (data[key] for key in ('orders','items','products','relationships'))
        cov=data['coverage']
        def integer(obj,key):
            v=obj[key]
            if type(v) is not int or v < 0: raise ValueError(f'invalid count: {key}')
            return v
        for row,keys in [(a,['n','unique_ids','null_keys']), (b,['n','unique_keys','null_keys','missing_product_id','invalid_price','invalid_freight','orders_with_items']), (c,['n','unique_ids','null_keys','missing_category']), (r,['orphan_items','unknown_products','items_missing_category','joined_item_rows','joined_unique_item_keys']), (cov,['missing_purchase'])]:
            for key in keys: integer(row,key)
        months=data['purchase_months_with_items']
        if type(months) is not int or months < 1: raise ValueError('invalid month count')
        try: amt=Decimal(str(b['item_price_sum']))
        except (InvalidOperation, TypeError): raise ValueError('invalid item total')
        if not amt.is_finite() or amt < 0: raise ValueError('invalid item total')
        if not cov['min_purchase'] or not cov['max_purchase']: raise ValueError('missing purchase coverage')
        if a['n'] != a['unique_ids'] or a['null_keys']: failures.append('ORDER_GRAIN')
        if b['n'] != b['unique_keys'] or b['null_keys']: failures.append('ITEM_GRAIN')
        if c['n'] != c['unique_ids'] or c['null_keys']: failures.append('PRODUCT_GRAIN')
        if r['joined_item_rows'] != b['n'] or r['joined_unique_item_keys'] != b['n']: failures.append('JOIN_FANOUT')
        if r['orphan_items'] or r['unknown_products'] or b['missing_product_id']: failures.append('RELATIONSHIP_COVERAGE')
        if b['invalid_price'] or b['invalid_freight']: failures.append('INVALID_ITEM_VALUES')
        if cov['missing_purchase']: failures.append('MISSING_PURCHASE_DATE')
        if b['orders_with_items'] > a['n'] or b['orders_with_items'] > b['n']: failures.append('IMPOSSIBLE_POPULATION')
        if c['missing_category'] or r['items_missing_category']: warnings.append('MISSING_CATEGORY_REQUIRES_UNKNOWN_BUCKET')
        if b['orders_with_items'] < a['n']: warnings.append('ORDERS_WITHOUT_ITEMS_EXCLUDED_FROM_ITEM_METRICS')
    except (KeyError,TypeError,ValueError) as exc:
        failures.append('INVALID_AUDIT_PAYLOAD: '+str(exc))
    return {'status':'PRODUCT_RELATIONSHIP_AUDIT_PASSED' if not failures else 'PRODUCT_RELATIONSHIP_AUDIT_FAILED',
            'failures':failures,'warnings':warnings,'counts':{
                'orders':data.get('orders',{}).get('n') if isinstance(data.get('orders'),dict) else None,
                'items':data.get('items',{}).get('n') if isinstance(data.get('items'),dict) else None,
                'products':data.get('products',{}).get('n') if isinstance(data.get('products'),dict) else None},
            'approved_for_mcp':False,'inventory_claim_allowed':False,'causal_claim':False,
            'next_gate':'Audit month-level measures, category completeness, item units vs distinct orders and MCP contracts; stockouts require separately validated inventory evidence.'}


def main():
    if len(sys.argv)!=2: raise SystemExit('Usage: python -m scripts.phase4c18_assess path/to/audit.json')
    try:
        raw=Path(sys.argv[1]).read_text(encoding='utf-8-sig')
        result=assess(json.loads(raw))
    except Exception as exc:
        result={'status':'PRODUCT_RELATIONSHIP_AUDIT_FAILED','failures':[str(exc)],'approved_for_mcp':False}
    print(json.dumps(result,indent=2))
    if result['status']!='PRODUCT_RELATIONSHIP_AUDIT_PASSED': raise SystemExit(1)
if __name__=='__main__': main()
