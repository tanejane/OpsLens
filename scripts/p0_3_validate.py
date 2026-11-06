"""Actual FastAPI HTTP session tests with real recovery/executors and mocked MCP/model boundaries."""
import asyncio
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
import json
from pathlib import Path
import re
import threading
import time
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient
import api
from investigation_sessions import SessionStore, COOKIE
from scripts.phase5_1_playground import InvestigationRuntime, new_recovery_session
from agent.phase5_1_unified import UnifiedSession
from agent.phase4c1_router import RoutingProposal
from agent.phase4b57_nl_dynamic_finance import Intent
from agent.session_context import period
from scripts.phase4b56_validate_dynamic import fixtures
from agent.phase4b1_semantic_playground import call as _warm_mcp_import


class Router:
    def propose(self,q,_): return RoutingProposal('test',('ranking' if 'sellers' in q.lower() else 'period_comparison' if 'compare' in q.lower() else 'metric_lookup',))


class Interpreter:
    def interpret(self,q,prior):
        from agent.phase4c25_clarification import MONTH_RE
        dates = [period(*m) for m in MONTH_RE.findall(q)]
        metric = 'effective_contribution_profit' if 'profit' in q.lower() else 'effective_revenue'
        kw = {'intent':'compare' if len(dates)==2 else 'measure','metric_id':metric,
            'start_date':dates[-1][0],'end_date_exclusive':dates[-1][1]}
        if len(dates)==2: kw.update(comparison_start_date=dates[0][0],comparison_end_date_exclusive=dates[0][1])
        return Intent(**kw)


class SessionHTTPTests(unittest.TestCase):
    def test_canonical_numeric_encodings_survive_session_and_storage_rejection(self):
        from decimal import Decimal
        async def measured(*args, **kwargs):
            return {'status':'MEASURED_WITH_SCOPE_LIMITS','executable':True,'causal_claim':False,
                'evidence':{'amount':Decimal('123.4500'),'reference':2**60},'limitations':['Fixture scope only']}
        id = self.create()
        with patch.object(InvestigationRuntime,'investigate',measured):
            response = self.turn(id,'Revenue in March 2018')
            self.assertEqual(response.status_code,200)
            record = response.json()['canonical_result']
            self.assertEqual(record['number_encodings'],{'/payload/evidence/amount':'decimal','/payload/evidence/reference':'integer'})
            self.assertEqual(record['payload']['evidence']['amount'],'123.4500')
            self.assertEqual(self.snapshot(id)['last_validated_result'],record)
            self.store.max_bytes = 1
            rejected = self.turn(id,'Revenue in April 2018')
            self.assertEqual(rejected.status_code,413)
            completed = rejected.json()['detail']['canonical_result']['payload']['completed_result']
            self.assertEqual(completed['number_encodings'],record['number_encodings'])
            self.assertEqual(self.snapshot(id)['last_validated_result'],record)

    def setUp(self):
        self.now = 100.0
        self.store = SessionStore(clock=lambda:self.now)
        self.calls = []
        self.fail_mcp = False
        self.block = False
        self.block_sync = False
        self.started,self.release = threading.Event(),threading.Event()
        parent = self
        class MCP:
            async def __aexit__(self,*args): pass
            async def call_tool(self,name,args):
                parent.calls.append((name,deepcopy(args)))
                if parent.block_sync:
                    parent.block_sync=False
                    parent.started.set()
                    parent.release.wait(5)
                if parent.block:
                    parent.block = False
                    parent.started.set()
                    await asyncio.to_thread(parent.release.wait,5)
                if parent.fail_mcp: raise RuntimeError('synthetic MCP outage')
                data = fixtures()
                profit = 15 if '2018-03-01' in args['query'] and '2018-04-01' in args['query'] else 20
                data['finance']['profit']=profit;data['daily']['profit']=profit
                purpose=args['purpose']
                if purpose=='Governed semantic graph analysis':
                    return SimpleNamespace(structured_content={'ok':True,'data':{'rows':[{'seller_id':'synthetic-seller','metric_value':160}]},'meta':{'fixture':True}})
                if purpose.startswith('4C15'):
                    row={'eligible_orders':100,'distinct_orders':100,'lateness_eligible_orders':90,'late_orders':9,
                        'duration_eligible_orders':90,'missing_actual':10,'missing_estimated':0,'missing_purchase':0,
                        'invalid_duration':0,'invalid_late_flags':0,'mean_delivery_days':'12.5','late_rate_pct':'10','lateness_coverage_pct':'90'}
                elif purpose.startswith('Finance period integrity: '): row=data[purpose.split(': ')[1]]
                else: row={'eligible_source_rows':8,'metric_value':profit if purpose.endswith('effective_contribution_profit') else 100}
                return SimpleNamespace(structured_content={'ok':True,'data':{'rows':[row]},'meta':{'row_count':1,'fixture':True}})
        async def open_runtime(**kwargs):
            from agent.phase4b43_graph_planner import GraphPlanner
            from scripts.phase4c2_validate_routing import Interpreter as GraphInterpreter
            client=MCP()
            planner=GraphPlanner(Path(__file__).resolve().parents[1]/'reports/phase4b42_relationship_audit.json')
            runtime=InvestigationRuntime(client,UnifiedSession(new_recovery_session(),gemini_enabled=False),Router(),Interpreter(),GraphInterpreter(),None,planner,None)
            return runtime,client
        self.patches=[patch.object(api,'sessions',self.store),patch('scripts.phase5_1_playground.open_investigation_runtime',open_runtime)]
        for p in self.patches:p.start()
        self.client=TestClient(api.app);self.client.__enter__()

    def tearDown(self):
        self.release.set();self.client.__exit__(None,None,None)
        for p in reversed(self.patches):p.stop()

    def create(self,client=None):
        response=(client or self.client).post('/api/investigation-sessions')
        self.assertEqual(response.status_code,200,response.text)
        return response.json()['session']['id']

    def snapshot(self,id,client=None):
        response=(client or self.client).get('/api/investigation-sessions/'+id)
        self.assertEqual(response.status_code,200,response.text)
        return response.json()['session']

    def turn(self,id,q,client=None,revision=None):
        client=client or self.client
        if revision is None:revision=self.snapshot(id,client)['revision']
        return client.post('/api/investigations',json={'question':q,'session_id':id,'revision':revision})

    def test_profit_clarification_then_contextual_comparison(self):
        id=self.create()
        first=self.turn(id,'Why did profit decline in March 2018?')
        self.assertEqual(first.json()['result']['status'],'NEEDS_CLARIFICATION')
        self.assertEqual(self.calls,[])
        reply=self.turn(id,'Compare that with February')
        self.assertEqual(reply.status_code,200,reply.text)
        result=reply.json()['result']
        self.assertEqual(result['evidence']['metric_id'],'effective_contribution_profit')
        self.assertEqual(result['evidence']['comparison']['absolute_change'],'-5')
        self.assertEqual(result['evidence']['before']['period'],['2018-02-01','2018-03-01'])
        self.assertEqual(result['evidence']['measurement']['period'],['2018-03-01','2018-04-01'])
        self.assertEqual(len(self.calls),10)
        self.assertFalse(result['causal_claim'])
        self.assertEqual(reply.json()['canonical_result'],self.snapshot(id)['last_validated_result'])
        self.assertIn('verification_checks',result['evidence']['measurement'])
        context=self.store.entries[id].recovery.language_session.product_session.prior.unified_state.conversation.finance
        self.assertEqual(context.metric_id,'effective_contribution_profit')
        self.assertEqual(context.start_date,'2018-03-01')
        self.assertEqual(result['context_provenance']['pending_source_turn'],1)

    def test_existing_sales_clarification_is_reused(self):
        id=self.create()
        self.assertEqual(self.turn(id,'Sales in March 2018?').json()['result']['status'],'NEEDS_CLARIFICATION')
        self.assertEqual(self.snapshot(id)['clarification']['sales']['period'],'March 2018')
        response=self.turn(id,'financial revenue')
        self.assertEqual(response.status_code,200,response.text)
        self.assertEqual(response.json()['result']['evidence']['measurement']['value'],'100')
        self.assertIsNone(self.snapshot(id)['clarification']['sales'])

    def test_pending_correction_and_validated_period_followup(self):
        id=self.create()
        self.turn(id,'Why did profit decline in March 2018?')
        self.turn(id,'No, I meant April')
        self.assertEqual(self.snapshot(id)['clarification']['investigation']['period'][0],'2018-04-01')
        self.turn(id,'Compare that with February')
        response=self.turn(id,'What about May 2018?')
        self.assertEqual(response.status_code,200,response.text)
        self.assertEqual(response.json()['result']['evidence']['measurement']['period'][0],'2018-05-01')
        self.assertEqual(response.json()['result']['evidence']['metric_id'],'effective_contribution_profit')

    def test_unknown_context_does_not_invent_year_or_metric(self):
        id=self.create()
        result=self.turn(id,'Compare that with February').json()['result']
        self.assertEqual(result['status'],'NEEDS_CLARIFICATION')
        self.assertEqual(self.calls,[])
        self.assertIsNone(self.snapshot(id)['last_validated_result'])

    def test_delivery_context_routes_through_existing_comparison_and_keeps_trace(self):
        id=self.create()
        first=self.turn(id,'What was the late delivery rate in June 2018?')
        self.assertEqual(first.json()['result']['evidence']['metric_id'],'late_delivery_rate')
        response=self.turn(id,'Compare that with May')
        self.assertEqual(response.status_code,200,response.text)
        result=response.json()['result']
        self.assertEqual(result['before']['period'],['2018-05-01','2018-06-01'])
        self.assertEqual(result['after']['period'],['2018-06-01','2018-07-01'])
        self.assertEqual(len(result['execution_trace']),2)
        self.assertEqual(len(self.calls),3)

    def test_graph_context_preserves_registered_dimensions_without_finance_inheritance(self):
        id=self.create()
        first=self.turn(id,'Which five sellers received the most orders in June 2018?')
        self.assertEqual(first.status_code,200,first.text)
        self.assertEqual(first.json()['result']['route'],'graph_analytics')
        response=self.turn(id,'What about July?')
        self.assertEqual(response.status_code,200,response.text)
        result=response.json()['result']
        self.assertEqual(result['route'],'graph_analytics')
        self.assertEqual(result['evidence']['dimensions'],['seller_id'])
        self.assertEqual(result['evidence']['period'],['2018-07-01','2018-08-01'])
        self.assertEqual(len(self.calls),2)

    def test_marketing_followup_reuses_captured_evidence_without_deeper_claims(self):
        id=self.create()
        captured=json.loads((Path(__file__).resolve().parents[1]/'reports/phase5_3e_incidents_live_responses.json').read_text(encoding='utf-8-sig'))['responses']['INC_001']
        async def captured_turn(*args,**kwargs):return deepcopy(captured)
        with patch.object(InvestigationRuntime,'investigate',captured_turn):
            original=self.turn(id,'Investigate the recorded finance divergence').json()['canonical_result']
        result=self.turn(id,'Break down marketing expenses further.').json()['result']
        self.assertEqual(result['status'],'ACTIONABLE_EVIDENCE_GAP')
        self.assertFalse(result['executable'])
        self.assertTrue(result['supporting_evidence'])
        self.assertEqual(self.calls,[])
        self.assertEqual(self.snapshot(id)['last_validated_result'],original)
        self.assertEqual(result['context_provenance']['source_turn'],1)
        self.assertEqual(result['source_result'],original)

    def test_owner_cookie_required_for_get_turn_and_reset(self):
        id=self.create()
        with TestClient(api.app) as other:
            self.create(other)
            self.assertEqual(other.get('/api/investigation-sessions/'+id).status_code,404)
            self.assertEqual(other.post('/api/investigations',json={'question':'revenue','session_id':id,'revision':0}).status_code,404)
            self.assertEqual(other.delete('/api/investigation-sessions/'+id).status_code,404)
        with TestClient(api.app) as anonymous:
            self.assertEqual(anonymous.get('/api/investigation-sessions/'+id).status_code,404)

    def test_same_owner_sessions_do_not_inherit_each_other(self):
        a,b=self.create(),self.create()
        self.turn(a,'Why did profit decline in March 2018?')
        self.assertIsNone(self.snapshot(b)['clarification']['investigation'])
        self.assertEqual(self.turn(b,'Compare that with February').json()['result']['status'],'NEEDS_CLARIFICATION')
        self.assertEqual(self.calls,[])

    def test_expiration_and_reset_revoke_context(self):
        id=self.create();self.turn(id,'Why did profit decline in March 2018?')
        self.now+=1801
        self.assertEqual(self.client.get('/api/investigation-sessions/'+id).status_code,404)
        fresh=self.create()
        self.assertNotEqual(fresh,id)
        self.turn(fresh,'Sales in March 2018?')
        self.assertEqual(self.client.delete('/api/investigation-sessions/'+fresh).status_code,200)
        self.assertEqual(self.client.get('/api/investigation-sessions/'+fresh).status_code,404)
        self.assertIsNone(self.snapshot(self.create())['clarification']['sales'])

    def test_failed_turn_retains_validated_and_pending_state(self):
        id=self.create();self.turn(id,'What was revenue in March 2018?')
        self.turn(id,'Why did profit decline in March 2018?')
        original=self.snapshot(id)
        self.fail_mcp=True
        response=self.turn(id,'Compare that with February')
        self.assertEqual(response.status_code,503,response.text)
        current=self.snapshot(id)
        self.assertEqual(current['last_validated_result'],original['last_validated_result'])
        self.assertEqual(current['clarification'],original['clarification'])
        self.assertEqual(response.json()['detail']['canonical_result']['payload']['status'],'EXECUTION_FAILED')
        self.fail_mcp=False
        self.assertEqual(self.turn(id,'Compare that with February').status_code,200)

    def test_unsafe_request_does_not_clear_recovery_context(self):
        id=self.create();self.turn(id,'Sales in March 2018?')
        original=self.snapshot(id)['clarification']
        self.turn(id,'DROP TABLE orders;')
        self.assertEqual(self.snapshot(id)['clarification'],original)
        self.assertEqual(self.calls,[])

    def test_concurrent_same_session_conflicts_other_session_progresses(self):
        id=self.create();other=self.create()
        self.block=True
        with ThreadPoolExecutor(max_workers=1) as pool:
            running=pool.submit(self.turn,id,'What was revenue in March 2018?',None,0)
            self.assertTrue(self.started.wait(5))
            self.assertEqual(self.turn(id,'What was revenue in April 2018?',revision=0).status_code,409)
            self.assertEqual(self.client.delete('/api/investigation-sessions/'+id).status_code,409)
            self.assertEqual(self.turn(other,'Why did profit decline in March 2018?').status_code,200)
            self.release.set()
            self.assertEqual(running.result(timeout=10).status_code,200)
        count=len(self.calls)
        self.assertEqual(self.turn(id,'What was revenue in April 2018?',revision=0).status_code,409)
        self.assertEqual(len(self.calls),count)

    def test_synchronous_provider_wait_does_not_block_other_http_sessions(self):
        first,second=self.create(),self.create()
        self.block_sync=True
        with ThreadPoolExecutor(max_workers=1) as pool:
            pending=pool.submit(self.turn,first,'What was revenue in March 2018?',None,0)
            self.assertTrue(self.started.wait(5))
            started=time.monotonic()
            result=self.turn(second,'Why did profit decline in March 2018?')
            self.assertEqual(result.status_code,200)
            self.assertLess(time.monotonic()-started,2)
            self.release.set()
            self.assertEqual(pending.result(timeout=10).status_code,200)

    def test_retention_capacity_and_oversized_results_fail_explicitly(self):
        self.store.max_turns=2;self.store.max_sessions=2
        id=self.create();self.create()
        self.assertEqual(self.client.post('/api/investigation-sessions').status_code,429)
        for month in ('March','April','May'): self.turn(id,f'What was revenue in {month} 2018?')
        current=self.snapshot(id)
        self.assertEqual(len(current['history']),2)
        self.assertEqual(current['evicted_turns'],1)
        self.store.max_bytes=1
        response=self.turn(id,'What was revenue in June 2018?')
        self.assertEqual(response.status_code,413)
        self.assertIn('completed_result',response.json()['detail']['canonical_result']['payload'])
        for key in ("history","last_validated_result","revision","clarification","evicted_turns"):
            self.assertEqual(self.snapshot(id)[key],current[key])

    def test_csrf_origin_cookie_flags_and_read_only_restore(self):
        response=self.client.post('/api/investigation-sessions')
        self.assertIn('HttpOnly',response.headers['set-cookie'])
        self.assertIn('SameSite=strict',response.headers['set-cookie'])
        self.assertEqual(response.headers['cache-control'],'no-store')
        id=response.json()['session']['id']
        self.assertEqual(self.client.post('/api/investigations',headers={'Origin':'https://untrusted.example'},json={'session_id':id,'question':'revenue'}).status_code,403)
        self.snapshot(id);self.snapshot(id)
        self.assertEqual(self.calls,[])

    def test_cross_year_followup_and_future_decline_baseline_require_clarification(self):
        id=self.create()
        self.assertEqual(self.turn(id,'Compare profit from March 2018 to April 2019').status_code,200)
        count=len(self.calls)
        response=self.turn(id,'Compare that with February')
        self.assertEqual(response.json()['result']['status'],'NEEDS_CLARIFICATION')
        self.assertEqual(len(self.calls),count)
        fresh=self.create();self.turn(fresh,'Why did profit decline in March 2018?')
        response=self.turn(fresh,'Compare that with April 2018')
        self.assertEqual(response.json()['result']['status'],'NEEDS_CLARIFICATION')
        self.assertEqual(len(self.calls),count)

    def test_missing_revision_and_whitespace_cannot_change_pending_state(self):
        id=self.create();self.turn(id,'Why did profit decline in March 2018?')
        previous=self.snapshot(id)
        self.assertEqual(self.client.post('/api/investigations',json={'session_id':id,'question':'February'}).status_code,422)
        self.turn(id,'   ')
        self.assertEqual(self.snapshot(id)['clarification'],previous['clarification'])
        self.assertEqual(self.calls,[])

    def test_global_storage_budget_does_not_evict_another_owners_evidence(self):
        id=self.create();self.turn(id,'What was revenue in March 2018?')
        previous=self.snapshot(id)
        self.store.total_bytes=self.store.entries[id].size
        with TestClient(api.app) as other:
            second=self.create(other)
            self.assertEqual(self.turn(second,'What was revenue in April 2018?',other).status_code,413)
            self.assertEqual(self.snapshot(second,other)['revision'],0)
        self.assertEqual(self.snapshot(id)['last_validated_result'],previous['last_validated_result'])

    def test_secure_cookie_under_https(self):
        with TestClient(api.app,base_url='https://testserver') as secure:
            response=secure.post('/api/investigation-sessions')
            self.assertIn('Secure',response.headers['set-cookie'])
            self.assertEqual(secure.get('/api/investigation-sessions/'+response.json()['session']['id']).status_code,200)

    def test_cancel_clears_clarification_without_model_or_tool_execution(self):
        id=self.create();self.turn(id,'Why did profit decline in March 2018?')
        with patch('scripts.phase5_1_playground.open_investigation_runtime',side_effect=AssertionError('Cancellation must not open a runtime')):
            response=self.turn(id,'cancel')
        self.assertEqual(response.json()['result']['status'],'CANCELLED')
        self.assertIsNone(self.snapshot(id)['clarification']['investigation'])
        self.assertEqual(self.calls,[])

    def test_ambiguous_reply_retains_pending_period_and_legacy_recovery_has_priority(self):
        id=self.create();self.turn(id,'Why did profit decline in March 2018?')
        self.turn(id,'Can you explain that?')
        self.assertEqual(self.snapshot(id)['clarification']['investigation']['period'][0],'2018-03-01')
        self.turn(id,'Compare that with February')
        self.turn(id,'Sales in June 2018?')
        self.turn(id,'No, I meant July')
        self.assertEqual(self.snapshot(id)['clarification']['sales']['period'],'July 2018')
        result=self.turn(id,'financial revenue').json()['result']
        self.assertEqual(result['evidence']['metric_id'],'effective_revenue')
        self.assertEqual(result['evidence']['measurement']['period'][0],'2018-07-01')


if __name__=='__main__': unittest.main()
