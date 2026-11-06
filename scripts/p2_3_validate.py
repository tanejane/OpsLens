"""Refund correctness, adaptive behavior and actual HTTP/replay with mocked MCP."""
from copy import deepcopy
from decimal import Decimal
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from agent.refund_concentration import compile_plan,validate_initial,validate_detail,initial
from agent.phase4c15_delivery import DeliveryRejected
from agent.evidence_followup import candidates,extend
from agent.investigation_state import InvestigationState

def counts(orders,returned,refunded,events,amount,multi=0):
 return dict(orders=orders,returned_orders=returned,refunded_orders=refunded,events=events,refund_amount=str(amount),multi_item_orders=multi)
def summary():
 return dict(**counts(10,4,3,5,'60.50'),invalid_orders=0,invalid_events=0,duplicate_events=0,source_unlinked_events=2,source_types=['synthetic_fixture'])
def detail():
 return {'invalid_orders':0,'invalid_events':0,'duplicate_events':0,'invalid_items':0,
  'buckets':[dict(bucket='single_seller',**counts(7,2,2,3,'40.50',3)),dict(bucket='multi_seller',**counts(2,1,1,1,20,2)),dict(bucket='unknown',**counts(1,1,0,1,0))],
  'sellers':[dict(seller='a',**counts(5,1,1,2,'30.50',2)),dict(seller='b',**counts(2,1,1,1,10,1))]}
def evidence():return validate_initial(compile_plan('2018-07-01','2018-08-01'),summary())
def result():return {'route':'refund_concentration','status':'MEASURED_WITH_LIMITATIONS','executable':True,'causal_claim':False,'refund_intent':True,'evidence':evidence(),'limitations':[]}

class RefundTests(unittest.IsolatedAsyncioTestCase):
 def test_exact_partition_multi_item_and_event_counts(self):
  proof=validate_detail(compile_plan('2018-07-01','2018-08-01',True),detail(),evidence())
  self.assertEqual(proof['population']['return_rate_pct'],'40')
  self.assertEqual(proof['sellers'][0]['returned_orders'],1)
  self.assertEqual(proof['sellers'][0]['events'],2)
  self.assertEqual(proof['sellers'][0]['multi_item_orders'],2)
  self.assertEqual(proof['sellers'][0]['return_rate_pct'],'20')
  self.assertEqual(Decimal(proof['sellers'][0]['share_of_all_refunds_pct']),Decimal(3050)/Decimal('60.50'))
  self.assertEqual(proof['buckets']['multi_seller']['refund_amount'],'20')
  self.assertEqual(proof['buckets']['unknown']['returned_orders'],1)
 def test_ranking_changes_with_evidence(self):
  row=detail();row['sellers'][0]['refund_amount']='5';row['sellers'][1]['refund_amount']='35.50'
  proof=validate_detail(compile_plan('2018-07-01','2018-08-01',True),row,evidence())
  self.assertEqual(proof['sellers'][0]['seller_id'],'b')
 def test_repository_csv_independent_order_aggregation(self):
  # Independent source-row oracle: no use of compiler SQL or aggregate fixtures.
  import csv
  from collections import defaultdict
  def rows(path):
   with open(path,encoding='utf-8-sig',newline='') as f:return list(csv.DictReader(f))
  all_orders=rows('data/raw/olist/olist_orders_dataset.csv')
  selected={o['order_id'] for o in all_orders if '2018-07-01'<=o['order_purchase_timestamp']<'2018-08-01'}
  returns=rows('data/synthetic/returns.csv');linked=defaultdict(list);items=defaultdict(list)
  for r in returns:
   if r['order_id'] in selected:linked[r['order_id']].append(r)
  for item in rows('data/raw/olist/olist_order_items_dataset.csv'):
   if item['order_id'] in selected:items[item['order_id']].append(item)
  self.assertEqual(len({r['return_id'] for group in linked.values() for r in group}),sum(map(len,linked.values())))
  from collections import Counter
  event_ids=Counter(r['return_id'] for r in returns)
  self.assertTrue(all(event_ids[r['return_id']]==1 for group in linked.values() for r in group))
  def aggregate(ids):
   return counts(len(ids),sum(bool(linked[o]) for o in ids),sum(sum(Decimal(r['refund_amount']) for r in linked[o])>0 for o in ids),sum(len(linked[o]) for o in ids),sum((Decimal(r['refund_amount']) for o in ids for r in linked[o]),Decimal(0)),sum(len(items[o])>1 for o in ids))
  buckets=defaultdict(set);sellers=defaultdict(set)
  for o in selected:
   ss={i['seller_id'] for i in items[o]}
   key='unknown' if not ss or '' in ss else 'multi_seller' if len(ss)>1 else 'single_seller'
   buckets[key].add(o)
   if key=='single_seller':sellers[next(iter(ss))].add(o)
  row=summary();row.update(aggregate(selected))
  known={o['order_id'] for o in all_orders};row['source_unlinked_events']=sum(r['order_id'] not in known for r in returns)
  row['source_types']=sorted({r['source_type'] for group in linked.values() for r in group})
  first=validate_initial(compile_plan('2018-07-01','2018-08-01'),row)
  breakdown={'invalid_orders':0,'invalid_events':0,'duplicate_events':0,'invalid_items':0,
   'buckets':[dict(bucket=k,**aggregate(v)) for k,v in buckets.items()],
   'sellers':[dict(seller=k,**aggregate(v)) for k,v in sellers.items()]}
  proof=validate_detail(compile_plan('2018-07-01','2018-08-01',True),breakdown,first)
  self.assertGreater(first['population']['returned_orders'],0)
  self.assertEqual(sum(Decimal(b['refund_amount']) for b in proof['buckets'].values()),Decimal(first['population']['refund_amount']))
  Path('reports/p2_3_csv_check.json').write_text(json.dumps({'scope':'Offline independent aggregation of repository CSV rows; not PostgreSQL execution','initial':first,'detail':proof},indent=2),encoding='utf-8')
 def test_invalid_identifiers_amounts_and_duplicate_events(self):
  for field in ('invalid_orders','invalid_events','duplicate_events'):
   row=summary();row[field]=1
   with self.assertRaises(DeliveryRejected):validate_initial(compile_plan('2018-07-01','2018-08-01'),row)
  for amount in ('NaN','-1','Infinity'):
   row=summary();row['refund_amount']=amount
   with self.assertRaises(DeliveryRejected):validate_initial(compile_plan('2018-07-01','2018-08-01'),row)
 def test_reconciliation_and_population_mismatch(self):
  for mutate in (lambda r:r['sellers'][0].update(orders=6),lambda r:r['sellers'][0].update(refund_amount='30.51'),lambda r:r['sellers'][0].update(seller=None),lambda r:r['sellers'].append(deepcopy(r['sellers'][0])),lambda r:r['buckets'][1].update(bucket='unknown')):
   row=detail();mutate(row)
   with self.assertRaises(DeliveryRejected):validate_detail(compile_plan('2018-07-01','2018-08-01',True),row,evidence())
  with self.assertRaises(DeliveryRejected):validate_detail(compile_plan('2018-08-01','2018-09-01',True),detail(),evidence())
  row=detail();row['invalid_items']=1
  with self.assertRaises(DeliveryRejected):validate_detail(compile_plan('2018-07-01','2018-08-01',True),row,evidence())
 def test_compiler_contract_and_no_sku_allocation(self):
  from mcp_server.runtime_tools import _validate_select_sql as validate_sql
  for detailed in (False,True):
   plan=compile_plan('2018-07-01','2018-08-01',detailed)
   validate_sql(plan['sql'])
   self.assertNotIn('product_id',plan['sql'])
  self.assertNotIn('order_items',compile_plan('2018-07-01','2018-08-01')['sql'])
  self.assertIn("WHERE bucket='single_seller'",compile_plan('2018-07-01','2018-08-01',True)['sql'])
  plan=compile_plan('2018-07-01','2018-08-01');plan['sql']+='; DELETE FROM cx.returns'
  with self.assertRaises(DeliveryRejected):validate_initial(plan,summary())
 def test_context_clarification_and_boundaries(self):
  from agent.refund_routing import contextual
  known={'route':'refund_concentration','period':['2018-07-01','2018-08-01'],'years':['2018'],'refund_intent':True}
  action,_,_=contextual('Which sellers',known,{})
  self.assertEqual(action['start'],'2018-07-01');self.assertTrue(action['detail'])
  action,_,_=contextual('What about August',known,{})
  self.assertEqual(action['start'],'2018-08-01')
  self.assertIsNone(contextual('Why did profit decline in March 2018',known,{}))
  self.assertIsNone(contextual('Return revenue for March 2018',known,{}))
  _,blocked,_=contextual('Which SKU caused refunds in July 2018',{},{});self.assertEqual(blocked['status'],'NOT_YET_SUPPORTED')
  action,_,_=contextual('2018',{}, {'capability':'refund_concentration','question':'Where are refunds concentrated in July','detail':True})
  self.assertEqual(action['start'],'2018-07-01')
 async def test_conditional_branch_and_no_duplicates(self):
  calls=[]
  async def reader(*args):calls.append(args);return detail()
  r=result();self.assertEqual(len(candidates(r,set())),1)
  completed=await extend(r,reader,InvestigationState())
  self.assertEqual(len(calls),1);self.assertIn('refund_analysis',completed)
  self.assertEqual(candidates(r,{'refund_concentration'}),[])
  r['refund_intent']=False;await extend(r,reader,InvestigationState());self.assertEqual(len(calls),1)
  r['refund_intent']=True;r['evidence']['population']['returned_orders']=0
  self.assertEqual(candidates(r,set()),[])
 async def test_partial_failure_and_budget(self):
  async def failed(*args):raise TimeoutError()
  r=await extend(result(),failed,InvestigationState())
  self.assertEqual(r['evidence'],evidence());self.assertNotIn('refund_analysis',r)
  self.assertEqual(r['orchestration']['stop_reason'],'DEADLINE_REACHED')
  state=InvestigationState(max_steps=1);state.begin('initial','test')
  r=await extend(result(),failed,state)
  self.assertEqual(r['orchestration']['stop_reason'],'STEP_BUDGET_REACHED')
 async def test_http_context_replay_and_canonical_preservation(self):
  import api
  from investigation_traces import TraceStore
  from scripts.p0_3_validate import SessionHTTPTests
  h=SessionHTTPTests();h.setUp();calls=[]
  async def query(client,sql,purpose,trace=None):
   calls.append(purpose)
   if trace is not None:trace.append({'tool':'run_readonly_sql','arguments':{'query':sql},'fixture':True})
   return detail() if 'exclusive-seller' in purpose else summary()
  try:
   with tempfile.TemporaryDirectory() as tmp,patch.object(api,'traces',TraceStore(Path(tmp)/'trace.sqlite3')),patch('scripts.phase5_1_playground.mcp_query',query):
    sid=h.create();response=h.turn(sid,'Where are refunds concentrated in July 2018?')
    self.assertEqual(response.status_code,200,response.text)
    record=response.json()['canonical_result'];self.assertEqual(len(calls),2)
    self.assertEqual(record['payload']['refund_analysis']['sellers'][0]['seller_id'],'a')
    run=record['payload']['observability']['run_id']
    self.assertEqual(h.client.get(f'/api/investigation-sessions/{sid}/runs/{run}/replay').json()['canonical_result'],record)
    self.assertEqual(len(calls),2)
    follow=h.turn(sid,'What about August?').json()['canonical_result']
    self.assertEqual(follow['payload']['evidence']['period'],['2018-08-01','2018-09-01'])
    self.assertEqual(h.snapshot(sid)['last_validated_result'],follow)
    Path('frontend/tests/fixtures/p2_3_refunds.json').write_text(json.dumps(record,indent=2),encoding='utf-8')
  finally:h.tearDown()

 async def test_source_scale_http_with_existing_session_bound(self):
  self.test_repository_csv_independent_order_aggregation()
  source=json.loads(Path('reports/p2_3_csv_check.json').read_text())
  first={**source['initial']['population'],'invalid_orders':0,'invalid_events':0,'duplicate_events':0,
   'source_unlinked_events':source['initial']['source_unlinked_events'],'source_types':source['initial']['source_types']}
  detailed={'invalid_orders':0,'invalid_events':0,'duplicate_events':0,'invalid_items':0,
   'buckets':[dict(bucket=k,**v) for k,v in source['detail']['buckets'].items()],
   'sellers':[dict(seller=s['seller_id'],**{k:v for k,v in s.items() if k!='seller_id'}) for s in source['detail']['sellers']]}
  import api
  from investigation_traces import TraceStore
  from scripts.p0_3_validate import SessionHTTPTests
  h=SessionHTTPTests();h.setUp()
  async def query(client,sql,purpose,trace=None):
   row=detailed if 'exclusive-seller' in purpose else first
   # Preserve the full MCP response, as the real runtime does.
   if trace is not None:trace.append({'tool':'run_readonly_sql','arguments':{'query':sql},'response':{'ok':True,'data':{'rows':[deepcopy(row)]}}})
   return deepcopy(row)
  try:
   with tempfile.TemporaryDirectory() as tmp,patch.object(api,'traces',TraceStore(Path(tmp)/'trace.sqlite3')),patch('scripts.phase5_1_playground.mcp_query',query):
    sid=h.create();response=h.turn(sid,'Where are refunds concentrated in July 2018?')
    self.assertEqual(response.status_code,200,response.text[:500])
    record=response.json()['canonical_result']
    self.assertEqual(record['payload']['refund_analysis']['sellers'],source['detail']['sellers'])
    self.assertEqual(h.snapshot(sid)['last_validated_result'],record)
    run=record['payload']['observability']['run_id']
    self.assertEqual(h.client.get(f'/api/investigation-sessions/{sid}/runs/{run}/replay').json()['canonical_result'],record)
    self.assertLess(h.store.entries[sid].size,h.store.max_bytes)
  finally:h.tearDown()

if __name__=='__main__':unittest.main()
