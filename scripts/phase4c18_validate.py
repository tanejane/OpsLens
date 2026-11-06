"""Deterministic contract tests; no database needed."""
import copy
from scripts.phase4c18_assess import assess

def fixture():
 return {'audit_version':'4C18_V1','sources':{'orders':'commerce.orders','items':'commerce.order_items','products':'catalog.products'},'orders':{'n':3,'unique_ids':3,'null_keys':0},'items':{'n':2,'unique_keys':2,'null_keys':0,'missing_product_id':0,'invalid_price':0,'invalid_freight':0,'orders_with_items':2,'item_price_sum': '20.0'},'products':{'n':2,'unique_ids':2,'null_keys':0,'missing_category':0},'relationships':{'orphan_items':0,'unknown_products':0,'items_missing_category':0,'joined_item_rows':2,'joined_unique_item_keys':2},'coverage':{'missing_purchase':0,'min_purchase':'2018-01-01','max_purchase':'2018-01-02'},'purchase_months_with_items':1,'audit_only':True,'approved_for_mcp':False,'inventory_evidence_available':False,'causal_claim':False}

def main():
 cases=[]
 cases.append(('valid',lambda d:None,True))
 def mut(path,val):
  def change(d):
   x=d
   for key in path[:-1]: x=x[key]
   x[path[-1]]=val
  return change
 for name,path,val in [
 ('duplicate orders',['orders','unique_ids'],2),('duplicate items',['items','unique_keys'],1),('duplicate products',['products','unique_ids'],1),
 ('missing item key',['items','null_keys'],1),('orphan items',['relationships','orphan_items'],1),('unknown product',['relationships','unknown_products'],1),
 ('join fanout',['relationships','joined_item_rows'],3),('join unique violation',['relationships','joined_unique_item_keys'],1),
 ('invalid price',['items','invalid_price'],1),('invalid freight',['items','invalid_freight'],1),('missing purchase',['coverage','missing_purchase'],1),
 ('impossible population',['items','orders_with_items'],4),('empty time',['coverage','min_purchase'],None),
 ('missing month',['purchase_months_with_items'],0),('bad sum',['items','item_price_sum'],'NaN'),
 ('inventory falsely available',['inventory_evidence_available'],True),('mcp falsely authorized',['approved_for_mcp'],True),
 ('causality falsely claimed',['causal_claim'],True),('not audit only',['audit_only'],False),('bad source',['sources','products'],'public.products'),
 ('bool count',['items','n'],True),('negative count',['products','n'],-1)]:
  cases.append((name,mut(path,val),False))
 for name,path,val in [('missing categories',['products','missing_category'],1),('unclassified items',['relationships','items_missing_category'],1)]:
  cases.append((name,mut(path,val),True))
 for name,modify,should_pass in cases:
  d=fixture();modify(d);r=assess(d);passed=r['status']=='PRODUCT_RELATIONSHIP_AUDIT_PASSED'
  assert passed==should_pass,(name,r)
  assert r['approved_for_mcp'] is False and r['inventory_claim_allowed'] is False and r['causal_claim'] is False
  print('PASS:',name)
 print(f'Checks passed: {len(cases)}/{len(cases)}')
if __name__=='__main__':main()
