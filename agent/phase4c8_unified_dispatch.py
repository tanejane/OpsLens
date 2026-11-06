"""Discovery preflight for the existing Phase 4C.7 unified dispatcher.

IMPORTANT: For supported finance investigations it does not bypass the Gemini
period grounding or the audited finance executor. For other question types,
it delegates unchanged to the already validated routes. It never executes
non-governed capabilities just because the catalogue lists them.
"""
from agent.phase4c7_unified_dispatch import dispatch as prior_dispatch
from agent.phase4c1_router import validate_route, needs_reference_clarification
from agent.phase4c8_planning import PlanningRequest, plan


async def dispatch(question, state, router, finance_interpreter, finance_reader,
                   graph_interpreter, planner, graph_reader, investigation_interpreter):
    if needs_reference_clarification(question):
        return await prior_dispatch(question, state, router, finance_interpreter,
                                    finance_reader, graph_interpreter, planner,
                                    graph_reader, investigation_interpreter)
    proposal = router.propose(question, state.conversation)
    route = validate_route(proposal)
    class FixedRouter:
        def propose(self, _question, _context):
            return proposal
    if route.route == 'investigation':
        # 'Financial divergence' comes from the same governed NL investigation
        # grounding path as 4C.7. We attach *discovery metadata* only after it
        # returns; missing baseline does not become an assumed baseline.
        result, updated_state = await prior_dispatch(question,state,FixedRouter(),
            finance_interpreter,finance_reader,graph_interpreter,planner,
            graph_reader,investigation_interpreter)
        periods = result.get('periods') if isinstance(result,dict) else None
        confirmed_periods = bool(isinstance(periods,dict) and
            all(isinstance(periods.get(s),list) and len(periods[s])==2 for s in ('before','after')))
        result = {**result,'capability_discovery':plan(PlanningRequest(
            'financial_divergence',explicit_periods=confirmed_periods))}
        return result,updated_state
    return await prior_dispatch(question,state,FixedRouter(),finance_interpreter,
                                finance_reader,graph_interpreter,planner,
                                graph_reader,investigation_interpreter)
