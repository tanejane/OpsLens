"""Phase 4C.7 bounded, evidence-directed investigation coordinator.

Uses only existing audited operations. No LLM SQL, invented baseline or causal
attribution. A deterministic capability planner, NOT autonomous cross-domain
reasoning. Every query goes via the supplied MCP read-only adapter.
"""
from __future__ import annotations

from decimal import Decimal, InvalidOperation
from copy import deepcopy
from agent.phase4c6_nl_investigation import ground_interpretation
from agent.phase4c3_investigation import investigate
from agent.phase4c4_drivers import discover_drivers
from agent.phase4c5_hypotheses import evaluate_hypotheses

class AdaptiveRejected(ValueError):
    pass


def _dec(value):
    try:
        number = Decimal(str(value))
    except (InvalidOperation, ValueError, TypeError) as exc:
        raise AdaptiveRejected('Invalid evidence number') from exc
    if not number.is_finite():
        raise AdaptiveRejected('Nonfinite evidence number')
    return number


def _per_order(core, discovery, *, tolerance=Decimal('0.05')):
    """Compare verified component intensities, not infer campaign performance.

    Called only after independently reconciled component evidence was accepted.
    """
    if discovery.get('status') != 'RECONCILED_COMPONENT_BREAKDOWN':
        raise AdaptiveRejected('Cost components not reconciled')
    periods = discovery.get('period_evidence', {})
    before, after = periods.get('before'), periods.get('after')
    if not isinstance(before, dict) or not isinstance(after, dict):
        raise AdaptiveRejected('Period evidence missing')
    observations = {}
    for side, proof in [('before', before), ('after', after)]:
        if proof.get('period') != core['periods'][side] or proof.get('reconciliation') != 'RECONCILED_FOR_REVIEW' or proof.get('source') != 'semantic.order_cost_components':
            raise AdaptiveRejected('Inconsistent period evidence')
        n = proof.get('source_population_rows')
        if isinstance(n, bool) or not isinstance(n, int) or n <= 0:
            raise AdaptiveRejected('Invalid order population')
        for metric in ('effective_revenue','effective_cogs','effective_contribution_profit'):
            m = core['evidence'][metric][side]
            if m.get('source_population_rows') != n or m.get('period') != proof['period'] or m.get('source') != 'semantic.order_economics' or m.get('period_reconciliation_status') != 'RECONCILED_FOR_REVIEW':
                raise AdaptiveRejected('Finance proof population or period disagreement')
        observations[side] = n
    result = []
    for item in discovery.get('components', []):
        key = item['component']
        prev = _dec(item['before']) / observations['before']
        curr = _dec(item['after']) / observations['after']
        result.append({'component': key, 'before_per_order': str(prev), 'after_per_order': str(curr),
                       'change_per_order': str(curr-prev), 'causal_claim': False})
    return {'status': 'RECONCILED_INTENSITY_COMPARISON', 'population_basis': 'financially eligible orders with items',
            'before_orders': observations['before'], 'after_orders': observations['after'],
            'components': result, 'causal_claim': False,
            'limitations': ['Per-order averages reflect different order cohorts and do not identify causality',
                            'Financial charge data include modeled or synthetic values']}


async def adaptive_investigation(question, interpreter, reader, *, max_steps=3, max_hypotheses=5,
                                 investigate_fn=investigate, driver_fn=discover_drivers,
                                 evaluate_fn=evaluate_hypotheses):
    """Bounded evidence-driven steps: premise -> drivers -> per-order context.

    No arbitrary action proposals. Audit trace describes why each registered
    capability was or was not invoked. Failed/unreconciled details fail closed.
    """
    if isinstance(max_steps, bool) or not isinstance(max_steps, int) or not 1 <= max_steps <= 3:
        raise AdaptiveRejected('Step budget must be 1..3')
    proposal = interpreter.interpret(question)
    request, blocked = ground_interpretation(question, proposal)
    if blocked is not None:
        return {**blocked, 'adaptive': {'steps_used': 0, 'trace': [], 'stop_reason': 'GROUNDING_REJECTED'}}
    assert request is not None
    trace = []
    core = await investigate_fn(request, reader)
    if core.get('route') != 'investigation' or core.get('executable') is not True or core.get('causal_claim') is not False:
        raise AdaptiveRejected('Invalid governed premise result')
    # Core validates its own independently audited finance evidence.
    premise = core.get('premise', {})
    if not isinstance(premise, dict) or not isinstance(premise.get('divergence_confirmed'), bool):
        raise AdaptiveRejected('Missing audited premise')
    trace.append({'step': 1, 'capability': 'premise_and_accounting_bridge', 'decision': 'EXECUTED',
                  'reason': 'Required to verify question before examining drivers'})
    payload = deepcopy(core)
    payload['investigation_status'] = core['status']
    if not premise['divergence_confirmed']:
        payload.update(status='PREMISE_NOT_CONFIRMED',
                       adaptive={'steps_used': len(trace), 'trace': trace, 'stop_reason': 'CLAIM_CONTRADICTED_BY_FINANCE',
                                 'unsupported': ['Operational causality','Campaign incrementality','Product mix profit allocation']})
        return payload
    if max_steps == 1:
        payload.update(status='PARTIAL_EVIDENCE_BUDGET',
                       adaptive={'steps_used': 1, 'trace': trace, 'stop_reason': 'STEP_BUDGET_EXHAUSTED'})
        return payload
    # The core measures an accounting residual; a component breakdown is a
    # useful next tool only after its source scope has been reconciled.
    async def component_reader(sql, purpose):
        row = await reader(sql, purpose)
        if not isinstance(row, dict):
            raise AdaptiveRejected('Malformed MCP aggregate')
        return {'rows': [row]}
    try:
        expanded = await driver_fn(core, component_reader)
    except Exception as exc:
        payload.update(status='PARTIAL_GOVERNED_EVIDENCE',
            adaptive={'steps_used':len(trace),'trace':trace,'stop_reason':'COMPONENT_STEP_FAILED',
                'error_type':type(exc).__name__})
        payload['limitations']=[*payload.get('limitations',[]),'Cost-component inspection failed; the validated accounting bridge remains available.']
        return payload
    # Preserve the original stage, including its then-current caveats, and all
    # component proofs. Ranking is a presentation subset, not an evidence store.
    payload['stage_results'] = {'premise_and_accounting_bridge': deepcopy(core),
                                'reconciled_cost_components': deepcopy(expanded)}
    payload['driver_discovery'] = deepcopy(expanded.get('driver_discovery', {}))
    discovery = expanded.get('driver_discovery', {})
    trace.append({'step': 2, 'capability': 'reconciled_cost_components', 'decision': discovery.get('status'),
                  'reason': 'Unexplained net-charge movement warrants approved cost-component inspection'})
    if discovery.get('status') != 'RECONCILED_COMPONENT_BREAKDOWN':
        payload.update(status='INSUFFICIENT_GOVERNED_EVIDENCE',
                       adaptive={'steps_used': len(trace), 'trace': trace, 'stop_reason': 'COST_COMPONENT_EVIDENCE_UNAVAILABLE',
                                 'unavailable_reason': discovery.get('reason', 'No verified component data')})
        return payload
    try:
        evaluation = evaluate_fn(expanded, max_hypotheses=max_hypotheses)
    except Exception as exc:
        payload.update(status='PARTIAL_GOVERNED_EVIDENCE',adaptive={'steps_used':len(trace),'trace':trace,
            'stop_reason':'EVALUATION_FAILED','error_type':type(exc).__name__})
        return payload
    if evaluation.get('status') != 'EVIDENCE_RANKED_NOT_CAUSAL' or evaluation.get('causal_claim') is not False:
        raise AdaptiveRejected('Evaluation did not prove its evidence contract')
    payload['hypothesis_evaluation'] = evaluation
    # Core caveats described the pre-discovery stage; retain them there without
    # presenting its 'components not yet verified' claim as the final outcome.
    payload['limitations'] = deepcopy(discovery.get('limitations', [])) + deepcopy(evaluation.get('limitations', []))
    payload.pop('next_step', None)
    payload.pop('hypotheses_not_tested', None)
    if max_steps == 2:
        payload.update(status='EVIDENCE_RANKED_NOT_CAUSAL',
                       adaptive={'steps_used': len(trace), 'trace': trace, 'stop_reason': 'STEP_BUDGET_EXHAUSTED',
                                 'untested': evaluation.get('untested',{})})
        return payload
    # Third step is selected only when a measured financial cost pressure is
    # present; it probes per-order intensity using the already reconciled rows.
    pressure = [h for h in evaluation['hypotheses'] if h.get('disposition') == 'SUPPORTS_PROFIT_PRESSURE']
    if pressure:
        try:
            intensity = _per_order(expanded, discovery)
        except AdaptiveRejected as exc:
            payload.update(status='EVIDENCE_RANKED_NOT_CAUSAL',adaptive={'steps_used':len(trace),'trace':trace,
                'stop_reason':'INTENSITY_EVIDENCE_REJECTED','error_type':type(exc).__name__})
            return payload
        payload['order_normalized_evidence'] = intensity
        trace.append({'step': 3, 'capability': 'per_order_intensity', 'decision': 'EXECUTED_NO_NEW_SQL',
                      'reason': 'Test whether total cost pressures can be explained solely by greater order volume'})
    payload.update(status='EVIDENCE_RANKED_NOT_CAUSAL',
                   adaptive={'steps_used': len(trace), 'trace': trace,
                             'stop_reason': 'NO_MORE_APPROVED_HYPOTHESIS_TOOLS',
                             'untested': evaluation.get('untested', {}),
                             'causal_claim': False})
    return payload
