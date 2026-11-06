"""Offline adaptive acceptance tests with real metric validators."""
import asyncio
import json
import unittest
from copy import deepcopy
from pathlib import Path
from agent.delivery_review_comparison import validate,compile_comparison
from agent.evidence_followup import extend
from agent.investigation_state import InvestigationState,BudgetStop
from scripts.p1_1_validate import fixture

def delivery_row():
    return dict(eligible_orders=12,distinct_orders=12,lateness_eligible_orders=11,late_orders=5,
        duration_eligible_orders=11,missing_actual=1,missing_estimated=0,missing_purchase=0,
        invalid_duration=0,invalid_late_flags=0,mean_delivery_days='10',late_rate_pct=str(500/11),lateness_coverage_pct=str(1100/12))

def review_row():
    return dict(eligible_orders=14,distinct_orders=14,reviewed_orders=10,low_rating_orders=3,multi_review_orders=1,
        average_score='3.5',low_rating_rate_pct='30',review_coverage_pct=str(1000/14),invalid_scores=0,invalid_flags=0)

def initial(row=None):
    return {'route':'delivery_review_comparison','status':'MEASURED_WITH_LIMITATIONS','executable':True,'causal_claim':False,
        'reason':'Late orders average one point lower.', 'limitations':['Descriptive only'],
        'evidence':validate(compile_comparison('2019-07-01','2019-08-01'),row or fixture())}

class AdaptiveTests(unittest.IsolatedAsyncioTestCase):
    async def run_case(self,row=None,**budgets):
        self.calls=[]
        state=InvestigationState(**budgets);state.begin('initial','test');state.trace[-1]['decision']='VALIDATED'
        async def reader(sql,purpose):
            self.calls.append(purpose)
            return delivery_row() if purpose.startswith('4C15') else review_row()
        result=await extend(initial(row),reader,state)
        return result
    async def test_sufficient_stops(self):
        row=fixture();row['total']=11;row['missing_review_rows']=0;row['cohorts'].pop()
        result=await self.run_case(row)
        self.assertEqual(self.calls,[]);self.assertEqual(result['orchestration']['stop_reason'],'QUESTION_ADDRESSED')
    async def test_evidence_changes_action(self):
        result=await self.run_case()
        self.assertEqual([s['capability'] for s in result['supporting_analyses']],['delivery_missingness','review_population_coverage'])
        row=fixture();row['total']=11;row['cohorts'].pop()
        result=await self.run_case(row)
        self.assertEqual([s['capability'] for s in result['supporting_analyses']],['review_population_coverage'])
        self.assertIn('broader population',result['conclusions'][-1])
    async def test_failure_retains_initial(self):
        async def fail(*args):raise RuntimeError('offline')
        source=initial();state=InvestigationState();state.begin('initial','test')
        result=await extend(source,fail,state)
        self.assertEqual(result['evidence'],source['evidence']);self.assertFalse(result['causal_claim'])
        self.assertEqual(result['orchestration']['stop_reason'],'FOLLOWUP_UNAVAILABLE_OR_CONTRADICTORY')
    async def test_contradiction_rejected(self):
        async def reader(*args):
            row=delivery_row();row['late_orders']=4;row['late_rate_pct']=str(400/11);return row
        state=InvestigationState();state.begin('initial','test')
        result=await extend(initial(),reader,state)
        self.assertNotIn('supporting_analyses',result)
    async def test_step_budget(self):
        result=await self.run_case(max_steps=1)
        self.assertEqual(self.calls,[]);self.assertEqual(result['orchestration']['stop_reason'],'STEP_BUDGET_REACHED')
    async def test_duplicate_query_and_tool_budget(self):
        state=InvestigationState(max_tools=1);calls=[]
        async def op():calls.append(1);return {'x':1}
        self.assertEqual(await state.read('query',op),await state.read('query',op))
        self.assertEqual(len(calls),1)
        with self.assertRaises(BudgetStop):await state.read('different',op)
        state.begin('same','test')
        with self.assertRaises(BudgetStop):state.begin('same','test')
    async def test_deadline(self):
        state=InvestigationState(seconds=.01)
        async def slow():await asyncio.sleep(.05)
        with self.assertRaises(TimeoutError):await state.read('slow',slow)
    async def test_partial_second_failure(self):
        async def reader(sql,purpose):
            if purpose.startswith('4C15'):return delivery_row()
            raise RuntimeError('unavailable')
        state=InvestigationState();state.begin('initial','test')
        result=await extend(initial(),reader,state)
        self.assertEqual(len(result['supporting_analyses']),1)
        self.assertEqual(result['evidence'],initial()['evidence'])
    async def test_finance_failure_retains_bridge(self):
        from agent.phase4c7_adaptive import adaptive_investigation
        from scripts.phase4c7_validate_adaptive import QUESTION,Interpreter,fake_core,reader
        async def fail(*args):raise RuntimeError('unavailable')
        result=await adaptive_investigation(QUESTION,Interpreter(),reader,investigate_fn=fake_core,driver_fn=fail)
        self.assertTrue(result['premise']['divergence_confirmed'])
        self.assertEqual(result['adaptive']['stop_reason'],'COMPONENT_STEP_FAILED')
    async def test_http_evidence_changes_tools_and_sessions_stay_isolated(self):
        from scripts.p0_3_validate import SessionHTTPTests
        from unittest.mock import patch
        harness=SessionHTTPTests();harness.setUp()
        rows=fixture();calls=[]
        async def query(client,sql,purpose,trace=None):
            calls.append(purpose)
            if purpose.startswith('4C15'):return delivery_row()
            if purpose.startswith('4C11'):return review_row()
            return deepcopy(rows)
        try:
            with patch('scripts.phase5_1_playground.mcp_query',query):
                first=harness.create();second=harness.create()
                expanded=harness.turn(first,'Compare late and on-time ratings in July 2019').json()['canonical_result']
                self.assertEqual(len(calls),3)
                rows['total']=11;rows['missing_review_rows']=0;rows['cohorts'].pop()
                sufficient=harness.turn(second,'Compare late and on-time ratings in September 2020').json()['canonical_result']
                self.assertEqual(len(calls),4)
                self.assertNotIn('supporting_analyses',sufficient['payload'])
                self.assertEqual(harness.snapshot(first)['last_validated_result'],expanded)
                follow=harness.turn(second,'What about October?').json()['canonical_result']
                self.assertEqual(follow['payload']['evidence']['period'],['2020-10-01','2020-11-01'])
                self.assertEqual(len(calls),5)
        finally:harness.tearDown()

if __name__=='__main__':unittest.main()
