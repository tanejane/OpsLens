"""Upgrade only investigation dispatch; preserve Phase4C.6 finance/graph state."""
from agent.phase4c1_router import validate_route, needs_reference_clarification
from agent.phase4c2_graph_routing import dispatch as existing_dispatch
from agent.phase4c7_adaptive import adaptive_investigation

async def dispatch(question, state, router, finance_interpreter, finance_reader,
                   graph_interpreter, planner, graph_reader, investigation_interpreter):
    if needs_reference_clarification(question):
        return await existing_dispatch(question,state,router,finance_interpreter,
                                       finance_reader,graph_interpreter,planner,graph_reader)
    proposal = router.propose(question, state.conversation)
    plan = validate_route(proposal)
    if plan.route == 'investigation':
        result = await adaptive_investigation(question, investigation_interpreter, finance_reader)
        return result,state  # Never overwrite successful finance/graph follow-up state.
    class FixedRouter:
        def propose(self, _question, _context):
            return proposal
    return await existing_dispatch(question,state,FixedRouter(),finance_interpreter,
                                   finance_reader,graph_interpreter,planner,graph_reader)
