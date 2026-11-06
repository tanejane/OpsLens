"""Additive routing hook: natural-language investigation + existing finance and graph."""
from agent.phase4c1_router import validate_route, needs_reference_clarification
from agent.phase4c2_graph_routing import dispatch as existing_dispatch
from agent.phase4c6_nl_investigation import run_investigation

async def dispatch(question, state, router, finance_interpreter, finance_reader,
                   graph_interpreter, planner, graph_reader, investigation_interpreter):
    # Let existing dispatcher own vague references and all successful finance/graph context.
    if needs_reference_clarification(question):
        return await existing_dispatch(question,state,router,finance_interpreter,
                                       finance_reader,graph_interpreter,planner,graph_reader)
    proposal=router.propose(question,state.conversation)
    plan=validate_route(proposal)
    if plan.route=='investigation':
        # Never commits an investigation-specific result to finance/graph context.
        return await run_investigation(question,investigation_interpreter,finance_reader),state
    class FixedRouter:
        def propose(self, _question, _context):return proposal
    return await existing_dispatch(question,state,FixedRouter(),finance_interpreter,
                                   finance_reader,graph_interpreter,planner,graph_reader)
