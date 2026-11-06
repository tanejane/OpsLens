from decimal import Decimal
from agent.phase4b52_reconciliation import Period,queries,result_for,summary,ReconciliationError

def sample():
 return {'population':{'placed_orders':10,'represented_orders':8,'unrepresented_orders':2,'missing_canceled':1,'missing_unavailable':1,'missing_other':0,'missing_status_null':0},
  'economics':{'financial_rows':8,'financial_unique_orders':8,'revenue':100,'cogs':60,'contribution_profit':20},
  'daily':{'daily_rows':3,'revenue':100,'cogs':60,'contribution_profit':20,'orders':8}}

def run():
 p=Period('2018-06-01','2018-07-01');checks=0
 def test(label,condition):
  nonlocal checks
  assert condition,label
  checks+=1;print('PASS:',label)
 x=sample();result=result_for(p,x)
 test('balanced population reconciled',result['status']=='RECONCILED_FOR_REVIEW')
 test('no automatic approval',not result['execution_approved'])
 test('gross ratio of sums',abs(result['measurements']['effective_gross_margin_pct']-40)<1e-8)
 test('contribution ratio of sums',abs(result['measurements']['effective_contribution_margin_pct']-20)<1e-8)
 x=sample();x['population']['missing_other']=1
 test('unexpected exclusions rejected',result_for(p,x)['status']=='DISCREPANCIES_FOUND')
 x=sample();x['daily']['revenue']=99
 test('daily financial mismatch caught',result_for(p,x)['status']=='DISCREPANCIES_FOUND')
 x=sample();x['economics']['financial_unique_orders']=7
 test('population mismatch caught',result_for(p,x)['status']=='DISCREPANCIES_FOUND')
 x=sample();x['economics']['revenue']=None
 test('null metric inconclusive',result_for(p,x)['status']=='INCONCLUSIVE')
 x=sample();x['population']['placed_orders']=0
 test('missing coverage rejected',result_for(p,x)['status']=='DISCREPANCIES_FOUND')
 test('SQL avoids item fanout',all('order_items' not in q for q in queries(p).values()))
 test('all queries bounded',all('LIMIT 1' in q for q in queries(p).values()))
 test('no unapproved identifiers',all('"semantic"' in q or '"commerce"' in q for q in queries(p).values()))
 try:Period('2018-07-01','2018-06-01');ok=False
 except ReconciliationError:ok=True
 test('invalid period blocked',ok)
 test('summary approval false',not summary([result])['execution_approved'])
 print(f'Checks passed: {checks}/{checks}')
if __name__=='__main__':run()
