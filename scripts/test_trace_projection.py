"""Offline tests: execute with python -m unittest scripts.test_trace_projection -v"""
import copy
import json
import unittest
from agent.investigation_result import investigation_response
from agent.trace_projection import project_agent_trace


class TraceProjectionTests(unittest.TestCase):
    def test_preserves_distinct_tool_calls(self):
        p = {'execution_trace': [
            {'tool': 'run_readonly_sql', 'outcome': 'RETURNED'},
            {'tool': 'run_readonly_sql', 'outcome': 'RETURNED'}]}
        events = project_agent_trace(p)['events']
        self.assertEqual([e['id'] for e in events], ['execution:0', 'execution:1'])

    def test_preserves_independent_stops(self):
        p = {'orchestration': {'stop_reason': 'EXISTING_COORDINATOR_COMPLETED'},
             'adaptive': {'stop_reason': 'PREMISE_NOT_CONFIRMED'}}
        result = project_agent_trace(p)
        self.assertEqual(len(result['stop_conditions']), 2)
        self.assertEqual(result['stop_conditions'][0]['source'], 'orchestration')
        self.assertEqual(result['stop_conditions'][1]['source'], 'adaptive')

    def test_excludes_raw_sql_and_tool_response(self):
        p = {'execution_trace': [{'tool': 'run_readonly_sql',
               'arguments': {'query': 'SELECT secret FROM private'},
               'response': {'data': {'secret': 'hidden'}}, 'outcome': 'RETURNED'}]}
        projected = json.dumps(project_agent_trace(p))
        self.assertNotIn('SELECT', projected)
        self.assertNotIn('secret', projected)
        self.assertNotIn('arguments', projected)
        self.assertNotIn('response', projected)

    def test_no_fabricated_global_order(self):
        p = {'orchestration': {'trace': [{'capability': 'finance', 'decision': 'EXECUTED'}]},
             'execution_trace': [{'tool': 'run_readonly_sql'}]}
        t = project_agent_trace(p)
        self.assertEqual(t['ordering'], 'SOURCE_LOCAL_ONLY')
        self.assertFalse(t['global_sequence_verified'])

    def test_invalid_entry_preserves_source_index(self):
        t = project_agent_trace({'execution_trace': [None, {}, {'tool': 'run_readonly_sql'}]})
        self.assertEqual(t['events'][0]['id'], 'execution:2')

    def test_response_integration_is_additive_and_lossless(self):
        original = {'status': 'EVIDENCE_RANKED_NOT_CAUSAL',
                    'financial_premise': {'revenue_delta': 139034.73},
                    'execution_trace': [{'tool': 'run_readonly_sql', 'outcome': 'RETURNED',
                                         'arguments': {'query': 'SELECT 1'}}],
                    'adaptive': {'stop_reason': 'COMPONENTS_RECONCILED'}}
        before = copy.deepcopy(original)
        body = investigation_response('What changed?', original)
        payload = body['canonical_result']['payload']
        self.assertEqual(original, before)
        self.assertEqual(body['result'], payload)
        self.assertEqual(payload['execution_trace'], original['execution_trace'])
        self.assertEqual(payload['financial_premise'], original['financial_premise'])
        self.assertEqual(payload['agent_trace_v2']['events'][0]['id'], 'execution:0')
        self.assertNotIn('SELECT', json.dumps(payload['agent_trace_v2']))
        self.assertEqual(payload['agent_trace_v2']['stop_conditions'][0]['source'], 'adaptive')

    def test_empty_and_clarification_responses_stay_valid(self):
        for status in ('NEEDS_CLARIFICATION', 'EXECUTION_FAILED'):
            payload = investigation_response('Question', {'status': status})['result']
            self.assertEqual(payload['status'], status)
            self.assertEqual(payload['agent_trace_v2']['events'], [])


if __name__ == '__main__':
    unittest.main()
