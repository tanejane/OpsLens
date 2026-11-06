"""Run as: python -m scripts.phase4b3_validate_relationships"""
from agent.phase4b3_relationship_governance import RelationshipRequest,compile_relationship,QueryRejected
O={'order_id':'text','order_purchase_timestamp':'text'}
I={'order_id':'text','seller_id':'text'}
M={'order_id':'text','category':'text','effective_revenue':'numeric','effective_cogs':'numeric'}
all_rel={'commerce.orders','commerce.order_items','semantic.product_mix_effective'}
checks=[]
def check(label,fn):
    fn();checks.append(label);print('PASS:',label)
def seller():
    q=RelationshipRequest(metric='unique_orders',dimension='seller_id',start_date='2018-06-01',end_date_exclusive='2018-07-01',limit=10)
    sql,c=compile_relationship(q,{'commerce.orders':O,'commerce.order_items':I},all_rel)
    assert 'COUNT(DISTINCT o."order_id")' in sql and 'ON o."order_id" = i."order_id"' in sql
    assert '2018-07-01' in sql and 'pg_input_is_valid' in sql and 'o.CASE' not in sql
    assert 'ORDER BY metric_value DESC' in sql
check('Unique orders per seller: correct join, distinct count and guarded dates',seller)
def category():
    q=RelationshipRequest(metric='gross_margin_pct',dimension='category',start_date='2018-06-01',end_date_exclusive='2018-07-01',order='asc')
    sql,c=compile_relationship(q,{'commerce.orders':O,'semantic.product_mix_effective':M},all_rel)
    assert 'SUM(m."effective_revenue") - SUM(m."effective_cogs")' in sql
    assert 'NULLIF(SUM(m."effective_revenue"),0)' in sql
    assert 'AVG(' not in sql and 'ORDER BY metric_value ASC' in sql
    assert 'ON m."order_id" = o."order_id"' in sql
check('Category gross margin: ratio of sums and lowest-first ordering',category)
def rejected():
    try: compile_relationship(RelationshipRequest(metric='unique_orders',dimension='category',start_date='2018-06-01',end_date_exclusive='2018-07-01'),{'commerce.orders':O},all_rel)
    except QueryRejected: return
    assert False,'unsupported pair should fail'
check('Unsupported metric-dimension combinations blocked',rejected)
def missing():
    try: compile_relationship(RelationshipRequest(metric='unique_orders',dimension='seller_id',start_date='2018-06-01',end_date_exclusive='2018-07-01'),{'commerce.orders':O,'commerce.order_items':{'seller_id':'text'}},all_rel)
    except QueryRejected: return
    assert False,'missing join key should fail'
check('Missing join key rejected',missing)
def approved():
    try: compile_relationship(RelationshipRequest(metric='unique_orders',dimension='seller_id',start_date='2018-06-01',end_date_exclusive='2018-07-01'),{'commerce.orders':O,'commerce.order_items':I},{'commerce.orders'})
    except QueryRejected: return
    assert False,'unapproved relation should fail'
check('Non-allowlisted relation rejected',approved)
def dates():
    try: RelationshipRequest(metric='unique_orders',dimension='seller_id',start_date='2018-07-01',end_date_exclusive='2018-06-01')
    except ValueError: return
    assert False
check('Invalid date boundaries rejected',dates)
print(f'Checks passed: {len(checks)}/{len(checks)}')
