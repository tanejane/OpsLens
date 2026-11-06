from scripts.phase4c11b_compare import compare
from decimal import Decimal
import copy
metrics={'average_review_score':{'value':'4.25'},'low_rating_rate':{'value':'20'},'review_coverage':{'value':'80'},'reviewed_order_count':{'value':'8'}}
population={'eligible_orders':10,'reviewed_orders':8,'low_rating_orders':2,'multi_review_orders':1}
audit={**population,'distinct_orders':10,'average_review_score':'4.25','low_rating_rate':'25','review_coverage':'80'}
metrics['low_rating_rate']['value']='25'
live={'status':'LIVE_MCP_VALIDATED','period':['2018-06-01','2018-07-01'],'population':population,'metrics':metrics}
count=0
def passcheck(name,fn):
 global count
 fn();count+=1;print('PASS:',name)
def rejects(name,fn):
 def run():
  try:fn()
  except (ValueError,KeyError,TypeError):return
  raise AssertionError('Must reject '+name)
 passcheck(name,run)
passcheck('valid reconciliation',lambda:compare(live,audit))
for k in population:
 a=copy.deepcopy(audit);a[k]+=1
 rejects('population mismatch '+k,lambda a=a:compare(live,a))
a=copy.deepcopy(audit);a['distinct_orders']=9
rejects('duplicate order grain',lambda:compare(live,a))
for k in metrics:
 l=copy.deepcopy(live);l['metrics'][k]['value']='999'
 rejects('metric mismatch '+k,lambda l=l:compare(l,audit))
l=copy.deepcopy(live);l['status']='LIVE_MCP_NOT_VALIDATED'
rejects('unverified MCP',lambda:compare(l,audit))
print(f'Checks passed: {count}/{count}')
