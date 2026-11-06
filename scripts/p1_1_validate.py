"""Offline cohort contracts and actual HTTP integration; no live measurements."""
import unittest
from copy import deepcopy
from unittest.mock import patch
from fastapi.testclient import TestClient
import api
from investigation_sessions import SessionStore
from agent.delivery_review_comparison import compile_comparison, validate
from agent.phase4c15_delivery import DeliveryRejected
from scripts.p0_3_validate import SessionHTTPTests

def fixture():
    return {'total':12,'invalid_grain':0,'misaligned':0,'invalid_scores':0,'missing_review_rows':1,
        'cohorts':[{'cohort':'late','orders':5,'reviewed':4,'low':2,'score_sum':'12','multi_review_orders':1},
        {'cohort':'on_time','orders':6,'reviewed':5,'low':1,'score_sum':'20','multi_review_orders':0},
        {'cohort':'unclassified','orders':1,'reviewed':0,'low':0,'score_sum':'0','multi_review_orders':0}]}

class ComparisonTests(unittest.TestCase):
    def setUp(self): self.plan=compile_comparison('2018-03-01','2018-04-01')
    def test_reconciled(self):
        result=validate(self.plan,fixture())
        self.assertEqual(result['late_minus_on_time_score'],'-1')
        self.assertEqual(result['cohorts']['late']['missing_reviews'],1)
        self.assertFalse(result['causal_claim'])
    def test_empty_reviews(self):
        row=fixture();row['cohorts'][0].update(reviewed=0,low=0,score_sum='0')
        self.assertIsNone(validate(self.plan,row)['late_minus_on_time_score'])
    def test_duplicate_or_misaligned_rejected(self):
        for key in ['invalid_grain','misaligned','invalid_scores']:
            row=fixture();row[key]=1
            with self.assertRaises(DeliveryRejected):validate(self.plan,row)
    def test_overlap_rejected(self):
        row=fixture();row['cohorts'].append(deepcopy(row['cohorts'][0]))
        with self.assertRaises(DeliveryRejected):validate(self.plan,row)
    def test_numeric_reconciliation(self):
        for key,value in [('orders',1),('reviewed',9),('low',6),('score_sum','NaN'),('score_sum','99')]:
            row=fixture();row['cohorts'][0][key]=value
            with self.assertRaises(DeliveryRejected):validate(self.plan,row)
    def test_plan_tampering(self):
        self.plan['sql']+='; SELECT 1'
        with self.assertRaises(DeliveryRejected):validate(self.plan,fixture())
    def test_clarification_and_model_gate(self):
        import asyncio
        from agent.delivery_review_routing import contextual,route
        action,_,_=contextual('2018',{}, {'capability':'delivery_review_comparison','question':'Compare late and on-time ratings in March'},None)
        self.assertEqual(action['start'],'2018-03-01')
        async def model(*args):return '{"start":"2019-03-01","end":"2019-04-01"}'
        async def reader(*args):self.fail('Unvalidated model period reached reader')
        result=asyncio.run(route('Compare late and on-time ratings in March 2018',reader,model))
        self.assertEqual(result['status'],'NEEDS_CLARIFICATION')
    def test_http_journey(self):
        harness=SessionHTTPTests();harness.setUp()
        calls=[]
        async def reader(client,sql,purpose,trace=None):
            calls.append(sql)
            if trace is not None:trace.append({'tool':'run_readonly_sql','fixture':True})
            from scripts.p1_2_validate import delivery_row,review_row
            if purpose.startswith('4C15'):return delivery_row()
            if purpose.startswith('4C11'):return review_row()
            return fixture()
        try:
            with patch('scripts.phase5_1_playground.mcp_query',reader):
                id=harness.create()
                first=harness.turn(id,'Do late deliveries have lower ratings in March 2018?')
                self.assertEqual(first.status_code,200,first.text)
                record=first.json()['canonical_result']
                self.assertEqual(record['payload']['evidence']['late_minus_on_time_score'],'-1')
                self.assertTrue(record['payload']['execution_trace'])
                follow=harness.turn(id,'What about February?').json()['canonical_result']
                self.assertEqual(follow['payload']['evidence']['period'][0],'2018-02-01')
                deeper=harness.turn(id,'Why?').json()['canonical_result']
                self.assertEqual(deeper['payload']['evidence'],follow['payload']['evidence'])
                self.assertEqual(len(calls),6)
                self.assertFalse(deeper['payload']['causal_claim'])
                self.assertEqual(harness.snapshot(id)['last_validated_result'],deeper)
        finally:harness.tearDown()

if __name__=='__main__': unittest.main()
