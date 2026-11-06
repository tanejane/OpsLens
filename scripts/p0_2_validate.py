"""Lossless contract regressions: captured real results plus labeled executor cases.

Run --write-fixtures explicitly to regenerate the frontend's shared fixture.
Normal validation is offline and never rewrites expected data.
"""
import asyncio
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import sys
import unittest
from unittest.mock import AsyncMock, patch

from agent.investigation_result import canonical_result, investigation_response
from agent.phase4c3_investigation import InvestigationState, verify_premise, decompose, compose
from agent.phase4c7_adaptive import adaptive_investigation
from agent.phase5_2_multidomain import synthesize, MultiDomainRejected
from agent.phase5_2c_three_domain import combine
from scripts.phase4c3_validate_investigation import one, fixture as finance_fixture
from scripts.phase4c4_validate_drivers import core as driver_core, response as component_response
from scripts.phase4c7_validate_adaptive import QUESTION, Interpreter
from scripts.phase5_2_validate import sample

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / 'frontend/tests/fixtures/p0_2_variants.json'
CAPTURE = ROOT / 'reports/phase5_3e_incidents_live_responses.json'


def core_result(confirmed=True):
    if not confirmed:
        state = InvestigationState(one(), observations=finance_fixture(rev1=700000, profit1=140000))
    else:
        proof = driver_core()['evidence']
        state = InvestigationState(one(), observations={key: {'before': pair['before'], 'measurement': pair['after']} for key, pair in proof.items()})
    verify_premise(state)
    decompose(state)
    return compose(state).result


async def adaptive(confirmed=True, **kwargs):
    async def core(_request, _reader): return deepcopy(core_result(confirmed))
    async def reader(sql, _purpose):
        return component_response('before' if '2018-02-01' in sql else 'after')['rows'][0]
    return await adaptive_investigation(QUESTION, Interpreter(), reader, investigate_fn=core, **kwargs)


async def cases():
    historical = json.loads(CAPTURE.read_text(encoding='utf-8-sig'))['responses']
    result = {f'captured_{key}': {'provenance': f'unchanged live capture: {CAPTURE.name}#/responses/{key}', 'result': value} for key, value in historical.items()}
    partial = next(value for value in historical.values() if value.get('status') == 'PARTIAL_GOVERNED_EVIDENCE' and value.get('observations'))
    metric = deepcopy(partial['observations'][0])
    result['single_metric'] = {'provenance': 'Exact observed metric subtree from the captured partial response; transport wrapper only.',
        'result': {'route': 'delivery_measure', 'status': metric['status'], 'executable': True, 'causal_claim': False, 'evidence': metric}}
    generated = await adaptive()
    contradictory = await adaptive(False)
    operational = synthesize([['2018-05-01','2018-06-01'], ['2018-06-01','2018-07-01']], sample())
    # Use the same period contracts for both domains without relabeling real data:
    # these are explicitly synthetic executor inputs from existing offline suites.
    buckets = sample()
    periods = list(generated['periods'].values())
    for bucket, period in zip(buckets, periods):
        for value in bucket.values(): value['period'] = period
    cross = combine('Compare finance, delivery and reviews from February 2018 to March 2018', generated, synthesize(periods, buckets))
    from agent.phase4c2_graph_routing import validate_graph_response
    from agent.phase4b43_graph_planner import AnalysisRequest
    graph = validate_graph_response({'rows': [{'seller_id': 'synthetic-seller', 'metric_value': 160}]},
        {'sources': ['commerce.orders','commerce.order_items'], 'relationships': ['orders_to_items'], 'safety': 'distinct orders protected'},
        AnalysisRequest('unique_orders', ('seller_id',), '2018-06-01', '2018-07-01', 'desc', 5))
    finance = core_result()['evidence']['effective_revenue']
    for name, value in {
        'adaptive': generated, 'premise_contradiction': contradictory, 'cross_domain': cross, 'operational': operational,
        'financial': {'route':'finance_compare','status':'MEASURED_WITH_SCOPE_LIMITS','executable':True,'causal_claim':False,
            'evidence': {'metric_id':'effective_revenue','before':finance['before'],'measurement':finance['after'],
                         'comparison': {'absolute_change':core_result()['premise']['revenue_delta'],'change_unit':'currency'}}},
        'graph': {'route':'graph_analytics','status':graph['status'],'executable':True,'causal_claim':False,'evidence':graph},
    }.items():
        result[name] = {'provenance':'Synthetic offline executor case; not a live capture. Uses existing validated test inputs and production composers.', 'result':value}
    for name, item in result.items():
        item['api_response'] = investigation_response(name, item['result'])
    return {'capture_sha256': hashlib.sha256(CAPTURE.read_bytes()).hexdigest(), 'cases':result}


class LosslessTests(unittest.IsolatedAsyncioTestCase):
    async def test_shared_fixture_matches_executor_outputs_and_unchanged_captures(self):
        self.assertEqual(json.loads(FIXTURE.read_text(encoding='utf-8')), await cases())

    async def test_all_captured_variants_survive_canonical_api_serialization(self):
        from fastapi.encoders import jsonable_encoder
        for key, case in (await cases())['cases'].items():
            with self.subTest(key=key):
                response = investigation_response(key, case['result'])
                serialized = json.loads(json.dumps(jsonable_encoder(response)))
                self.assertEqual(serialized['canonical_result']['payload'], case['result'])
                self.assertEqual(serialized['result'], case['result'])

    async def test_fastapi_endpoint_returns_complete_canonical_payload(self):
        import api
        from fastapi.testclient import TestClient
        value = (await adaptive())
        runtime = AsyncMock()
        runtime.investigate.return_value = value
        client = AsyncMock()
        with patch('scripts.phase5_1_playground.open_investigation_runtime', AsyncMock(return_value=(runtime, client))), patch('api._cohort_audit_for', return_value=None):
            with TestClient(api.app) as http:
                result = http.post('/api/investigations', json={'question': QUESTION})
        self.assertEqual(result.status_code, 200)
        self.assertEqual(result.json(), investigation_response(QUESTION, value))
        client.__aexit__.assert_awaited_once()

    async def test_adaptive_retains_full_bridge_and_all_component_proofs(self):
        result = await adaptive()
        core = core_result()
        self.assertEqual(result['evidence'], core['evidence'])
        self.assertEqual(result['findings'], core['findings'])
        self.assertEqual(result['stage_results']['premise_and_accounting_bridge'], core)
        self.assertEqual(len(result['driver_discovery']['components']), 6)
        self.assertEqual(len(result['hypothesis_evaluation']['hypotheses']), 5)
        self.assertEqual(len(result['order_normalized_evidence']['components']), 6)
        self.assertEqual(len(result['adaptive']['trace']), 3)

    async def test_early_stops_retain_premise_evidence(self):
        for confirmed, budget in ((False,3),(True,1),(True,2)):
            result = await adaptive(confirmed, max_steps=budget)
            self.assertEqual(result['evidence'], core_result(confirmed)['evidence'])
            self.assertEqual(result['findings'], core_result(confirmed)['findings'])
            self.assertIn('stop_reason', result['adaptive'])

    async def test_unavailable_components_retain_failure_and_valid_core(self):
        async def unavailable(core, _reader):
            return {**core, 'driver_discovery': {'status':'DRIVER_EVIDENCE_UNAVAILABLE','reason':'No verified rows','limitations':['Do not infer zero']}}
        result = await adaptive(driver_fn=unavailable)
        self.assertEqual(result['evidence'], core_result()['evidence'])
        self.assertEqual(result['driver_discovery']['limitations'], ['Do not infer zero'])
        self.assertEqual(result['adaptive']['stop_reason'], 'COST_COMPONENT_EVIDENCE_UNAVAILABLE')

    async def test_synthesis_preserves_each_denominator_and_unknown_source_fields(self):
        values = sample()
        values[0]['late_delivery_rate']['evidence_id'] = 'regression-only-id'
        values[0]['late_delivery_rate']['future_metadata'] = {'nested': {'value':'1.234567890123456789', 'limitation':'Exact scope é'}}
        result = synthesize([list(pair) for pair in __import__('scripts.phase5_2_validate',fromlist=['P']).P], values)
        self.assertEqual(result['measurements'], values)
        for key in values[0]:
            self.assertEqual(result['metric_changes'][key]['beforeEvidence'], values[0][key])
            self.assertEqual(result['metric_changes'][key]['afterEvidence'], values[1][key])
        values[0]['late_delivery_rate']['population']['eligible_orders'] = 1
        with self.assertRaises(MultiDomainRejected): synthesize([['2018-05-01','2018-06-01'],['2018-06-01','2018-07-01']],values)

    async def test_three_domain_keeps_full_financial_and_operational_results(self):
        data = (await cases())['cases']
        result = data['cross_domain']['result']
        self.assertEqual(result['domain_results']['finance'], data['adaptive']['result'])
        self.assertEqual(result['domain_results']['operations']['measurements'][0]['late_delivery_rate']['population']['eligible_orders'], 6873)
        self.assertEqual(result['domain_results']['finance']['evidence']['effective_revenue']['before']['source_population_rows'],6694)
        self.assertFalse(result['approved_for_mcp'])

    async def test_contract_snapshot_is_independent_and_does_not_certify(self):
        original = {'status':'FAILED','evidence':{'id':'test-only','nested':[None,{},[],False,'é']}}
        snapshot = canonical_result('question',original)
        original['evidence']['id'] = 'changed'
        self.assertEqual(snapshot['payload']['evidence']['id'],'test-only')
        self.assertEqual(snapshot['payload']['status'],'FAILED')

    async def test_decimal_and_large_integer_transport_is_exact(self):
        from decimal import Decimal
        record = canonical_result('precision', {'value': Decimal('1234567890.1234567890123456789'), 'evidence_id': 9007199254740993})
        self.assertEqual(record['payload'], {'value':'1234567890.1234567890123456789','evidence_id':'9007199254740993'})
        self.assertEqual(record['number_encodings'], {'/payload/value':'decimal','/payload/evidence_id':'integer'})
        with self.assertRaises(ValueError): canonical_result('invalid', {'value':float('nan')})

    async def test_core_retains_full_executor_metadata_not_only_period_values(self):
        observations = finance_fixture()
        observations['effective_revenue']['comparison'] = {'relative_change_pct':'16.46982','relative_change_note':'original denominator'}
        observations['effective_revenue']['future_field'] = {'id':'regression-only-executor-id'}
        state = InvestigationState(one(),observations=observations)
        verify_premise(state)
        decompose(state)
        result = compose(state).result
        self.assertEqual(result['metric_results'], observations)

    async def test_runtime_retains_mcp_envelope_and_resets_trace_between_turns(self):
        from scripts.phase5_1_playground import InvestigationRuntime
        from types import SimpleNamespace
        envelope = {'ok':True,'data':{'rows':[{'value':'12.3456789'}]},'meta':{'row_count':1,'source':'test-only'}}
        client = SimpleNamespace(call_tool=AsyncMock(return_value=SimpleNamespace(structured_content=envelope)))
        runtime = InvestigationRuntime(client,None,None,None,None,None,None,None)
        async def route(question, dispatch, reader, finance, **kwargs):
            self.assertEqual(await reader('test-only SQL','test-only purpose'), envelope['data']['rows'][0])
            return {'status':'MEASURED_WITH_SCOPE_LIMITS','executable':True,'causal_claim':False,'evidence':{'value':'12.3456789'}}
        with patch('scripts.phase5_1_playground.multi_domain_route',route):
            first = await runtime.investigate('first')
            second = await runtime.investigate('second')
        self.assertEqual(len(first['execution_trace']),1)
        self.assertEqual(len(second['execution_trace']),1)
        self.assertEqual(first['execution_trace'][0]['response'],envelope)

    async def test_real_cohort_audit_retains_raw_artifact_and_assessment(self):
        from agent.phase5_2f_cohort_evidence import apply_cohort_evidence
        from scripts.phase5_2d_assess import assess
        raw = json.loads((ROOT / 'phase5_2d_cohort_audit.json').read_text(encoding='utf-8-sig'))
        assessment = assess(raw)
        months = raw['month_pairs']
        report = {'status':'THREE_DOMAIN_DESCRIPTIVE_EVIDENCE','causal_claim':False,'approved_for_mcp':False,
            'periods':{side:[month['month_start'],month['month_end']] for side, month in zip(('before','after'),months)},
            'cohort_orders':{side:month['orders'] for side, month in zip(('before','after'),assessment['months'])},
            'next_validations':[],'limitations':[],'conclusions':[],'tool_trace':[]}
        result = apply_cohort_evidence(report,raw)
        self.assertEqual(result['operational_cohort_evidence']['source_artifact'],raw)
        self.assertEqual(result['operational_cohort_evidence']['assessment'],assessment)
        self.assertFalse(result['operational_cohort_evidence']['approved_for_mcp'])

    async def test_mcp_metadata_trace_does_not_change_read_result(self):
        from agent.phase4b1_semantic_playground import call
        from types import SimpleNamespace
        envelope = {'ok':True,'data':{'rows':[{'value':'1.234567890123456789'}]},'meta':{'row_count':1,'relations':['semantic.test'],'timeout_ms':20000}}
        client = SimpleNamespace(call_tool=AsyncMock(return_value=SimpleNamespace(structured_content=envelope)))
        trace=[]
        self.assertEqual(await call(client,'run_readonly_sql',{'query':'test-only'},trace=trace),envelope['data'])
        self.assertEqual(trace[0]['response'],envelope)

    async def test_later_failure_keeps_validated_steps_through_fastapi_503(self):
        import api
        from fastapi.testclient import TestClient
        from scripts.phase5_1_playground import InvestigationRuntime
        from agent.phase4c2_graph_routing import validate_graph_response
        from agent.phase4b43_graph_planner import AnalysisRequest
        from agent.investigation_result import evidence_archive
        runtime = InvestigationRuntime(None,None,None,None,None,None,None,None)
        async def failed_route(*args, **kwargs):
            validate_graph_response({'rows':[{'seller_id':'synthetic-seller','metric_value':160}]},
                {'sources':['commerce.orders','commerce.order_items'],'relationships':['orders_to_items'],'safety':'distinct orders protected'},
                AnalysisRequest('unique_orders',('seller_id',),'2018-06-01','2018-07-01','desc',5))
            raise RuntimeError('Later tool unavailable')
        with patch('scripts.phase5_1_playground.multi_domain_route',failed_route), patch(
            'scripts.phase5_1_playground.open_investigation_runtime',AsyncMock(return_value=(runtime,AsyncMock()))), patch('api._cohort_audit_for',return_value=None):
            with TestClient(api.app) as http:
                response = http.post('/api/investigations',json={'question':'test failure after measurement'})
        self.assertEqual(response.status_code,503)
        record = response.json()['detail']['canonical_result']
        self.assertEqual(record['payload']['status'],'EXECUTION_FAILED')
        self.assertFalse(record['payload']['executable'])
        self.assertEqual(record['payload']['validated_evidence'][0]['result']['rows'][0]['metric_value'],160)
        with evidence_archive() as fresh:
            self.assertEqual(fresh,[])

    async def test_archive_never_retains_rejected_validation(self):
        from agent.investigation_result import evidence_archive
        from agent.phase4c2_graph_routing import validate_graph_response, GraphRouteRejected
        from agent.phase4b43_graph_planner import AnalysisRequest
        with evidence_archive() as entries:
            with self.assertRaises(GraphRouteRejected):
                validate_graph_response({'rows':[]}, {}, AnalysisRequest('unique_orders',('seller_id',),'2018-06-01','2018-07-01','desc',5))
            self.assertEqual(entries,[])

    async def test_cleanup_failure_does_not_discard_completed_result(self):
        import api
        from fastapi.testclient import TestClient
        value = await adaptive()
        runtime, client = AsyncMock(), AsyncMock()
        runtime.investigate.return_value = value
        client.__aexit__.side_effect = RuntimeError('cleanup failed')
        with patch('scripts.phase5_1_playground.open_investigation_runtime',AsyncMock(return_value=(runtime,client))), patch('api._cohort_audit_for',return_value=None):
            with TestClient(api.app) as http:
                response = http.post('/api/investigations',json={'question':QUESTION})
        self.assertEqual(response.status_code,503)
        record = response.json()['detail']['canonical_result']
        self.assertEqual(record['payload']['completed_result'],value)
        self.assertFalse(record['payload']['executable'])


if __name__ == '__main__':
    if '--write-fixtures' in sys.argv:
        FIXTURE.write_text(json.dumps(asyncio.run(cases()), ensure_ascii=False, indent=2),encoding='utf-8')
        print(FIXTURE)
    else:
        unittest.main()
