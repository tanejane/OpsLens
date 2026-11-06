"""Offline seller contracts and real HTTP session integration."""
import unittest
from copy import deepcopy
from unittest.mock import patch
from agent.seller_concentration import compile_plan,validate
from agent.phase4c15_delivery import compile_metric,validate_metric,DeliveryRejected
from agent.evidence_followup import extend,candidates
from agent.investigation_state import InvestigationState
from scripts.p1_2_validate import delivery_row

def fixture():
    return {'total':12,'invalid_grain':0,'buckets':[
        {'bucket':'single_seller','orders':8,'eligible':7,'late':3},
        {'bucket':'multi_seller','orders':3,'eligible':3,'late':2},
        {'bucket':'unknown','orders':1,'eligible':1,'late':0}],
        'sellers':[{'seller':'a','orders':5,'eligible':4,'late':3},{'seller':'b','orders':3,'eligible':3,'late':0}]}
def initial():
    evidence=validate_metric(compile_metric('late_delivery_rate','2019-07-01','2019-08-01'),{'rows':[delivery_row()]})
    return {'route':'seller_concentration','status':'MEASURED_WITH_LIMITATIONS','seller_intent':True,'executable':True,'causal_claim':False,'evidence':evidence,'reason':'5 orders arrived late.','limitations':[]}

class SellerTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):self.plan=compile_plan('2019-07-01','2019-08-01')
    def test_partition(self):
        proof=validate(self.plan,fixture(),initial()['evidence'])
        self.assertEqual(proof['sellers'][0]['late_rate_pct'],'75')
        self.assertEqual(proof['sellers'][0]['share_of_single_seller_late_pct'],'100')
        self.assertEqual(proof['buckets']['multi_seller']['late'],2)
        self.assertFalse(proof['causal_claim'])
    def test_changed_distribution(self):
        row=fixture();row['sellers'][0]['late']=0;row['sellers'][1]['late']=3
        self.assertEqual(validate(self.plan,row,initial()['evidence'])['sellers'][0]['seller_id'],'b')
    def test_duplicates_missing_and_reconciliation(self):
        variants=[]
        row=fixture();row['invalid_grain']=1;variants.append(row)
        row=fixture();row['sellers'].append(deepcopy(row['sellers'][0]));variants.append(row)
        row=fixture();row['sellers'][0]['seller']=None;variants.append(row)
        row=fixture();row['sellers'][0]['late']=4;variants.append(row)
        row=fixture();row['buckets'][1]['orders']=4;variants.append(row)
        for row in variants:
            with self.assertRaises(DeliveryRejected):validate(self.plan,row,initial()['evidence'])
    def test_no_shared_attribution(self):
        self.assertIn('COUNT(DISTINCT seller_id)',self.plan['sql'])
        self.assertIn("WHERE bucket='single_seller'",self.plan['sql'])
        row=fixture();row['buckets'][0]['bucket']='multi_seller'
        with self.assertRaises(DeliveryRejected):validate(self.plan,row,initial()['evidence'])
    def test_intent_and_evidence_gate(self):
        result=initial();self.assertEqual(len(candidates(result,set())),1)
        result['seller_intent']=False;self.assertEqual(candidates(result,set()),[])
        result['seller_intent']=True;result['evidence']['population']['late_orders']=0
        self.assertEqual(candidates(result,set()),[])
    def test_all_late_orders_shared(self):
        row=fixture();row['sellers']=[]
        row['buckets']=[{'bucket':'multi_seller','orders':11,'eligible':10,'late':5},{'bucket':'unknown','orders':1,'eligible':1,'late':0}]
        proof=validate(self.plan,row,initial()['evidence'])
        self.assertEqual(proof['sellers'],[])
        self.assertEqual(proof['buckets']['multi_seller']['late'],5)
    def test_clarification_and_unsupported_metrics(self):
        from agent.seller_routing import contextual
        action,_,_=contextual('2019',{}, {'capability':'seller_concentration','question':'Seller delivery delays in July'})
        self.assertEqual(action['start'],'2019-07-01')
        action,blocked,_=contextual('Compare seller delivery ratings in July 2019',{}, {})
        self.assertIsNone(action);self.assertEqual(blocked['status'],'NOT_YET_SUPPORTED')
    def test_tampered_plan(self):
        self.plan['sql']+='; SELECT 1'
        with self.assertRaises(DeliveryRejected):validate(self.plan,fixture(),initial()['evidence'])
    async def test_partial_failure(self):
        async def reader(*args):raise RuntimeError('offline')
        state=InvestigationState();state.begin('initial','test')
        result=await extend(initial(),reader,state)
        self.assertEqual(result['evidence'],initial()['evidence'])
        self.assertEqual(result['orchestration']['stop_reason'],'FOLLOWUP_UNAVAILABLE_OR_CONTRADICTORY')
    async def test_http_followup(self):
        from scripts.p0_3_validate import SessionHTTPTests
        harness=SessionHTTPTests();harness.setUp();calls=[]
        async def query(client,sql,purpose,trace=None):
            calls.append(purpose)
            if trace is not None:trace.append({'tool':'run_readonly_sql','fixture':True})
            return fixture() if purpose.startswith('Governed single-seller') else delivery_row()
        try:
            with patch('scripts.phase5_1_playground.mcp_query',query):
                id=harness.create()
                response=harness.turn(id,'Are delivery delays concentrated among sellers in July 2019?')
                self.assertEqual(response.status_code,200,response.text)
                record=response.json()['canonical_result']
                self.assertEqual(record['payload']['seller_analysis']['sellers'][0]['seller_id'],'a')
                self.assertEqual(len(calls),2)
                follow=harness.turn(id,'What about August?').json()['canonical_result']
                self.assertEqual(follow['payload']['seller_analysis']['period'][0],'2019-08-01')
                self.assertEqual(harness.snapshot(id)['last_validated_result'],follow)
                self.assertTrue(follow['payload']['execution_trace'])
                self.assertEqual(len(follow['payload']['execution_trace']),follow['payload']['orchestration']['tools_used'])
        finally:harness.tearDown()

if __name__=='__main__':unittest.main()
