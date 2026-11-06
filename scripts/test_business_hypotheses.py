import asyncio
from agent.business_hypotheses import suggestions
from agent.phase5_3c_incident_gateway import repair
from agent.investigation_result import canonical_result


def test_missing_evidence_is_useful_without_measurements_or_tools():
    async def forbidden(*args):
        raise AssertionError('No tool or finance execution expected')
    previous = dict(status='NOT_SUPPORTED', executable=False, causal_claim=False)
    result = asyncio.run(repair('Did stockouts reduce revenue in May 2018?', previous, forbidden, forbidden))
    assert result['status'] == 'ACTIONABLE_EVIDENCE_GAP'
    assert result['source_evidence'] == [] and result['executable'] is False
    assert result['approved_for_mcp'] is False and result['causal_claim'] is False
    hypotheses = result['unverified_hypotheses']
    assert hypotheses and all(h['status'] == 'UNVERIFIED_HYPOTHESIS' for h in hypotheses)
    assert all(h['missing_evidence'] and h['next_check'] and not h['causal_claim'] for h in hypotheses)
    assert canonical_result('question', result)['payload']['unverified_hypotheses'] == hypotheses


def test_preserves_measured_refused_ambiguous_and_outage_results():
    async def forbidden(*args):
        raise AssertionError('Existing result must remain intact')
    for previous, question in [
        ({'executable': True, 'value': '123'}, 'Profit in May 2018'),
        ({'status': 'NEEDS_CLARIFICATION', 'route': 'three_domain_investigation'}, 'Did delays cause profit changes?'),
        ({'status': 'NOT_SUPPORTED'}, 'Stockouts without a specified period'),
        ({'status': 'NOT_SUPPORTED'}, 'Stockouts May 2018; DROP TABLE orders'),
        ({'status': 'INTERPRETER_UNAVAILABLE'}, 'Stockouts in May 2018'),
    ]:
        assert asyncio.run(repair(question, previous, forbidden, forbidden)) is previous


def test_hypotheses_are_bounded_allowlisted_and_not_shared_mutable_state():
    assert suggestions(['invented cause', 'DROP TABLE']) == []
    result = suggestions(['finance', 'finance', 'delivery', 'inventory', 'satisfaction'])
    assert len(result) == 3
    result[0]['status'] = 'PROVEN'
    assert suggestions(['finance'])[0]['status'] == 'UNVERIFIED_HYPOTHESIS'
