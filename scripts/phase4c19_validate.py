from decimal import Decimal
from agent.phase4c19_product import compile_metric,validate_metric,ProductRejected
import asyncio
BASE={'total_units':100,'unique_items':100,'total_orders':80,'total_gmv':'1000.0','invalid_items':0,'category_units':20,'category_unique_items':20,'category_orders':15,'category_gmv':'300.0','category_invalid_items':0}
checks=0
def ok(name,fn):
 global checks
 fn();checks+=1;print('PASS:',name)
def reject(fn):
 try:fn()
 except ProductRejected:return
 raise AssertionError('Expected ProductRejected')
def success(metric):
 p=compile_metric(metric,'2018-05-01','2018-06-01','health_beauty')
 return validate_metric(p,{'rows':[dict(BASE)]})
for m in ('category_order_count','units_sold','item_gmv','average_item_price','category_gmv_share'):
 ok('valid '+m,lambda m=m:assert_result(m)) if False else None
for m,expected in [('category_order_count','15'),('units_sold','20'),('item_gmv','300.0'),('average_item_price','15.0'),('category_gmv_share','30.0')]:
 ok('valid '+m, lambda m=m,expected=expected: (Decimal(success(m)['value'])==Decimal(expected) or (_ for _ in ()).throw(AssertionError(m))))
for name,kw in [('invalid metric',{'metric_id':'stockout_rate'}),('invalid date',{'start':'2018-02-30'}),('reversed date',{'start':'2018-06-01'}),('SQL injection date',{'start':"2018-05-01';--"}),('unsafe category',{'category':"x' OR true--"}),('empty category',{'category':''}),('nonstring category',{'category':None})]:
 def fail(kw=kw):
  args=dict(metric_id='item_gmv',start='2018-05-01',end='2018-06-01',category='health_beauty');args.update(kw);reject(lambda:compile_metric(**args))
 ok(name,fail)
p=compile_metric('item_gmv','2018-05-01','2018-06-01','health_beauty')
for name,key,value in [('duplicate keys','unique_items',99),('negative units','category_units',-1),('category exceeds total','category_units',101),('negative gmv','category_gmv','-1'),('gmv exceeds total','category_gmv','1001'),('invalid price','invalid_items',1),('invalid category item','category_invalid_items',1),('nonfinite gmv','total_gmv','NaN'),('boolean count','total_units',True),('inconsistent category keys','category_unique_items',19)]:
 def test(key=key,value=value):
  row=dict(BASE);row[key]=value;reject(lambda:validate_metric(p,{'rows':[row]}))
 ok(name,test)
ok('multiple rows',lambda:reject(lambda:validate_metric(p,{'rows':[dict(BASE),dict(BASE)]})))
ok('tampered plan',lambda:reject(lambda:validate_metric({**p,'sql':'SELECT 1'},{'rows':[dict(BASE)]})))
ok('missing population',lambda:reject(lambda:validate_metric(p,{'rows':[]})))
async def simulated():
 async def reader(sql,purpose):return dict(BASE)
 from agent.phase4c19_product import measure
 out=await measure('item_gmv','2018-05-01','2018-06-01','health_beauty',reader)
 assert out['value']=='300.0' and out['causal_claim'] is False
ok('reader integration',lambda:asyncio.run(simulated()))
print(f'Checks passed: {checks}/{checks}')
