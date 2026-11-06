"""Offline fail-closed category census and exact-name resolver regression checks."""
from copy import deepcopy
from decimal import Decimal
from agent.phase4c21_category_catalog import audit,CategoryResolver,CatalogRejected
sample={'contract':'opslens_product_categories_census_v1','source_product_count':3,'source_item_count':5,'source_item_gmv':'90.00','categories':[
 {'raw_category':None,'products':1,'item_units':1,'distinct_orders':1,'item_gmv':'10.00'},
 {'raw_category':'beleza_saude','products':1,'item_units':3,'distinct_orders':2,'item_gmv':'60.00'},
 {'raw_category':'other_category','products':1,'item_units':1,'distinct_orders':1,'item_gmv':'20.00'}]}
count=0
def passes(name,call):
 global count
 call();count+=1;print('PASS:',name)
def rejects(name,data,err):
 def run():
  try:audit(data)
  except CatalogRejected as e:assert str(e)==err,(name,str(e));return
  raise AssertionError('Unexpected acceptance '+name)
 passes(name,run)
def altered(f):
 d=deepcopy(sample);f(d);return d
def assert_eq(a,b):assert a==b,(a,b)
passes('audited catalog',lambda:assert_eq(audit(sample)['status'],'PRODUCT_CATEGORY_CATALOG_AUDITED'))
for name,fn,err in [
 ('wrong contract',lambda d:d.update(contract='bad'),'WRONG_CONTRACT'),
 ('missing rows',lambda d:d.update(categories=[]),'EMPTY_CATALOG'),
 ('duplicate names',lambda d:d['categories'].append(deepcopy(d['categories'][1])),'DUPLICATE_CATEGORY'),
 ('unsafe names',lambda d:d['categories'][1].update(raw_category='beleza_saude; DROP TABLE x'),'UNSAFE_CATEGORY'),
 ('product mismatch',lambda d:d.update(source_product_count=4),'PRODUCT_TOTAL_MISMATCH'),
 ('item mismatch',lambda d:d.update(source_item_count=6),'ITEM_TOTAL_MISMATCH'),
 ('money mismatch',lambda d:d.update(source_item_gmv='91.00'),'GMV_TOTAL_MISMATCH'),
 ('bool count',lambda d:d['categories'][1].update(item_units=True),'INVALID_COUNT'),
 ('negative items',lambda d:d['categories'][1].update(item_units=-1),'INVALID_COUNT'),
 ('too many orders',lambda d:d['categories'][1].update(distinct_orders=4),'INCONSISTENT_GRAIN'),
 ('no orders with items',lambda d:d['categories'][1].update(distinct_orders=0),'INCONSISTENT_GRAIN'),
 ('negative money',lambda d:d['categories'][1].update(item_gmv='-1'),'INVALID_MONEY'),
 ('fractional cents',lambda d:d['categories'][1].update(item_gmv='60.001'),'INVALID_MONEY'),
 ('nonfinite money',lambda d:d['categories'][1].update(item_gmv='NaN'),'INVALID_MONEY'),
 ('unexpected row key',lambda d:d['categories'][1].update(alias='guess'),'ROW_SHAPE'),
 ('missing verified category',lambda d:d['categories'][1].update(raw_category='new_category'),'VERIFIED_CATEGORY_MISSING'),
 ('null category nonzero gmvs',lambda d:d['categories'][0].update(item_units=0),'INCONSISTENT_GRAIN'),
]: rejects(name,altered(fn),err)
resolver=CategoryResolver(sample)
for source,expected in [('health and beauty','beleza_saude'),('health & beauty','beleza_saude'),('health_beauty','beleza_saude'),('beleza_saude','beleza_saude'),('other_category','other_category')]:
 passes('resolve '+source,lambda s=source,e=expected:assert_eq(resolver.resolve(s)['canonical_category'],e))
for source,err in [('other category','UNRECOGNIZED_CATEGORY'),('shoe products','UNRECOGNIZED_CATEGORY'),('','CATEGORY_REQUIRED'),('no;drop','UNRECOGNIZED_CATEGORY')]:
 def check(s=source,e=err):
  try:resolver.resolve(s)
  except CatalogRejected as x:assert_eq(str(x),e);return
  raise AssertionError('accepted '+s)
 passes('reject '+str(source),check)
print(f'Checks passed: {count}/{count}')
