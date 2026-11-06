import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from agent.phase4b1_semantic_query import QuerySpec, QueryRejected, compile_query,previous_window

approved={'cx.effective_reviews'}
cols={'review_score':'integer','order_purchase_timestamp':'timestamp without time zone','seller_id':'text'}
s=QuerySpec(relation='cx.effective_reviews',aggregate='avg',measure_column='review_score',date_column='order_purchase_timestamp',start_date='2018-06-01',end_date_exclusive='2018-07-01',compare_previous_period=True)
checks=[]
def check(name,condition):
 print(('PASS' if condition else 'FAIL')+': '+name); checks.append(condition)
sql=compile_query(s,cols,approved)
check('Governed bounded query compiled', 'AVG("review_score")' in sql and 'LIMIT 200' in sql)
p=previous_window(s)
check('Previous-month window inferred from explicit date',p.start_date=='2018-05-01' and p.end_date_exclusive=='2018-06-01')
for label,other in [
 ('Invented relation rejected',s.model_copy(update={'relation':'staging.olist_reviews'})),
 ('Invented column rejected',s.model_copy(update={'measure_column':'fake_score'})),
 ('Unsafe identifier rejected',s.model_copy(update={'group_by':['seller_id; DROP TABLE x']})),
 ('Non-numeric average rejected',s.model_copy(update={'measure_column':'seller_id'})),
]:
 try: compile_query(other,cols,approved); check(label,False)
 except QueryRejected: check(label,True)
try: QuerySpec(relation='cx.effective_reviews',aggregate='count',compare_previous_period=True)
except ValueError: check('Comparison without dates rejected',True)
else: check('Comparison without dates rejected',False)
print(f'Checks passed: {sum(checks)}/{len(checks)}')
if not all(checks): raise SystemExit(1)
