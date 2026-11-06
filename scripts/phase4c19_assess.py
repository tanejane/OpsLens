import json,sys
from decimal import Decimal

def assess(x):
 try:
  a,b=x['raw'],x['derived']
  errors=[]
  for k in ('units','keys','unknown_units'):
   if type(a[k]) is not int or type(b[k]) is not int or a[k]!=b[k]:errors.append('MISMATCH_'+k.upper())
  if Decimal(str(a['gmv']))!=Decimal(str(b['gmv'])):errors.append('GMV_MISMATCH')
  if a['units']<=0 or a['units']!=a['keys']:errors.append('ITEM_GRAIN')
  if x.get('approved_for_mcp') is not False or x.get('inventory_claim_allowed') is not False:errors.append('POLICY_VIOLATION')
  if type(x['months']) is not int or x['months']<=0:errors.append('PERIOD_COVERAGE')
  return {'status':'PRODUCT_METRIC_SOURCE_RECONCILED' if not errors else 'PRODUCT_METRIC_SOURCE_REJECTED','failures':errors,'june_units':b['units'],'june_item_gmv':str(b['gmv']),'june_unknown_category_units':b['unknown_units'],'purchase_months':x['months'],'approved_for_mcp':False,'inventory_claim_allowed':False,'next_gate':'Independently approve metric definitions and check MCP read role + SQL allowlist'}
 except (ValueError,KeyError,TypeError,ArithmeticError) as e:return {'status':'PRODUCT_METRIC_SOURCE_REJECTED','failures':['INVALID_AUDIT',str(e)]}
if __name__=='__main__':
 try:
  with open(sys.argv[1],encoding='utf-8-sig') as f:r=assess(json.load(f))
 except Exception as e:r={'status':'PRODUCT_METRIC_SOURCE_REJECTED','failures':[str(e)]}
 print(json.dumps(r,indent=2));sys.exit(0 if r['status']=='PRODUCT_METRIC_SOURCE_RECONCILED' else 1)
