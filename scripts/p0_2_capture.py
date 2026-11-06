"""Explicit read-only capture of real governed responses (never called by tests).

Fixed interpretations select existing executors; no Gemini or new SQL is used.
The transcript enables offline replay through the same validators/calculations.
"""
import argparse
import asyncio
import json
from pathlib import Path

from agent.phase4b1_semantic_playground import call
from agent.phase4b57_nl_dynamic_finance import execute, mcp_query
from agent.phase4b56_dynamic_period import requested_period
from agent.phase4c6_nl_investigation import Interpretation
from agent.phase4c7_adaptive import adaptive_investigation
from agent.phase4c15_delivery import measure
from agent.phase5_2c_three_domain import investigate as three_domain
from agent.phase4c2_graph_routing import execute_graph, UnifiedContext
from agent.phase4b43_graph_planner import GraphPlanner
from agent.phase4b44_context_grounding import Interpretation as GraphMeaning
from agent.investigation_result import evidence_archive

ROOT = Path(__file__).resolve().parents[1]


class FixedFinance:
    def __init__(self, before, after):
        self.before, self.after = before, after

    def interpret(self, _question):
        return Interpretation('diagnostic_investigation', before_start=self.before[0],
            before_end=self.before[1], after_start=self.after[0], after_end=self.after[1])


async def run_case(name, reader, graph_reader):
    before, after = ['2018-02-01', '2018-03-01'], ['2018-03-01', '2018-04-01']
    question = 'Why did revenue rise and contribution profit fall in March 2018 compared with February 2018?'
    if name == 'single_metric':
        evidence = await measure('late_delivery_rate', '2018-06-01', '2018-07-01', reader)
        return {'route': 'delivery_measure', 'status': evidence['status'], 'executable': True, 'evidence': evidence, 'causal_claim': False}
    if name == 'financial':
        evidence = await execute('effective_revenue', requested_period(*before), requested_period(*after), reader)
        return {'route': 'finance_compare', 'status': evidence['status'], 'executable': True, 'evidence': evidence, 'causal_claim': False}
    if name == 'graph':
        class FixedGraph:
            def interpret(self, *_):
                return GraphMeaning(intent='ranking', metric_id='unique_orders', dimensions=['seller_id'],
                    start_date='2018-06-01', end_date_exclusive='2018-07-01', order='desc', limit=5)
        result, _ = await execute_graph('Which five sellers received the most orders in June 2018?',
            UnifiedContext(), FixedGraph(), GraphPlanner(ROOT / 'reports/phase4b42_relationship_audit.json'), graph_reader)
        return result
    if name == 'premise_contradiction':
        before, after = ['2018-05-01', '2018-06-01'], ['2018-06-01', '2018-07-01']
        question = 'Why did revenue rise and contribution profit fall in June 2018 compared with May 2018?'
    async def finance(q, rd):
        return await adaptive_investigation(q, FixedFinance(before, after), rd)
    if name == 'cross_domain':
        return await three_domain('Compare finance, delivery and reviews from February 2018 to March 2018', reader, finance)
    return await finance(question, reader)


async def capture():
    from mcp import Client
    from mcp_server.server import mcp
    cases = {}
    async with Client(mcp) as client:
        for name in ('single_metric', 'financial', 'adaptive', 'cross_domain', 'premise_contradiction', 'graph'):
            transcript, trace = [], []
            async def reader(sql, purpose):
                row = await mcp_query(client, sql, purpose, trace=trace)
                transcript.append({'kind': 'aggregate', 'sql': sql, 'purpose': purpose, 'result': row})
                return row
            async def graph_reader(sql, request, plan):
                result = await call(client, 'run_readonly_sql', {'query': sql, 'purpose': 'Governed semantic graph analysis',
                    'expected_grain': 'grouped by ' + ','.join(request.dimensions), 'max_rows': request.limit, 'timeout_ms': 20000}, trace=trace)
                transcript.append({'kind': 'graph', 'sql': sql, 'result': result})
                return result
            with evidence_archive() as archive:
                result = await run_case(name, reader, graph_reader)
            cases[name] = {'result': {**result, 'execution_trace': trace, 'validated_evidence':archive}, 'transcript': transcript}
            print(name, result['status'], flush=True)
    historical = json.loads((ROOT / 'reports/phase5_3e_incidents_live_responses.json').read_text(encoding='utf-8-sig'))['responses']
    gap = next((key, value) for key, value in historical.items() if value.get('status') == 'ACTIONABLE_EVIDENCE_GAP')
    cases['evidence_gap'] = {'result': gap[1], 'transcript': [], 'source': f'reports/phase5_3e_incidents_live_responses.json#/responses/{gap[0]}'}
    destination = ROOT / 'frontend/tests/fixtures/p0_2_captured.json'
    destination.write_text(json.dumps({'provenance': 'Real read-only MCP/PostgreSQL results captured with scripts.p0_2_capture --live; fixed interpretation, no Gemini. Evidence gap is an unchanged historical response.', 'cases': cases}, indent=2, ensure_ascii=False), encoding='utf-8')
    print(destination, flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--live', action='store_true', required=True)
    parser.parse_args()
    asyncio.run(capture())
