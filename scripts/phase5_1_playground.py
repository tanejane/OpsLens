
"""Unified OpsLens CLI. --gemini is opt-in (calls actual API and costs tokens)."""

import argparse
import asyncio
import json
from pathlib import Path

from agent.phase5_2f_cohort_evidence import load_audit
from agent.phase5_3c_incident_gateway import repair as repair_incident
from agent.phase5_1_explanation import explain_result
from agent.business_reasoning import add_business_reasoning
from agent.phase5_1_unified import UnifiedSession, result as route_result
from agent.phase5_2e_multidomain_router import route as multi_domain_route
from agent.phase5_2c_three_domain import investigate as three_domain_investigate
from agent.phase4c7_adaptive import adaptive_investigation
from agent.phase4c27a_interpreter import gemini_client
from agent.phase4c26_recovery import RecoverySession
from agent.phase4c24_language import LanguageSession
from agent.phase4c20_product_nlp import ProductNLPSession
from agent.phase4c17_delivery_compare import DeliveryComparisonSession
from agent.phase4c8_unified_dispatch import dispatch as prior_dispatch
from agent.phase4c6_nl_investigation import GeminiInvestigationInterpreter
from agent.phase4c2_graph_routing import UnifiedContext
from agent.phase4c1_router import GeminiRouter
from agent.phase4b57_nl_dynamic_finance import Interpreter, mcp_query
from agent.phase4b44_gemini_interpreter import GeminiSemanticInterpreter
from agent.phase4b43_graph_planner import GraphPlanner


class ModelDisabled(RuntimeError):
    pass


class DisabledInterpreter:
    def propose(self, *args, **kwargs):
        raise ModelDisabled("Model interpretation is disabled for this run")

    interpret = propose


class InvestigationRuntime:
    """One MCP-backed turn through the same bounded routes as the CLI."""

    def __init__(
        self,
        client,
        session,
        router,
        finance,
        graph,
        investigation,
        planner,
        cohort_audit,
        explanation_client=None,
    ):
        self.client = client
        self.session = session
        self.router = router
        self.finance = finance
        self.graph = graph
        self.investigation = investigation
        self.planner = planner
        self.cohort_audit = cohort_audit
        self.explanation_client = explanation_client

    async def investigate(
        self,
        question,
        *,
        cohort_audit=None,
        context_action=None,
        budgets=None,
    ):
        from agent.investigation_result import (
            evidence_archive,
            canonical_result,
        )
        from agent.investigation_state import InvestigationState
        from agent.evidence_followup import extend
        from investigation_traces import model_metadata

        state = InvestigationState(**(budgets or {}))
        execution_trace = []

        with evidence_archive() as archive, model_metadata() as models:
            try:
                state.begin(
                    "initial_governed_investigation",
                    "Resolve the question through existing governed routes",
                )

                result = await asyncio.wait_for(
                    self._investigate(
                        question,
                        cohort_audit=cohort_audit,
                        execution_trace=execution_trace,
                        context_action=context_action,
                        state=state,
                    ),
                    timeout=state.remaining(),
                )

                state.trace[-1]["decision"] = "COMPLETED"

                async def reader(sql, purpose):
                    return await state.read(
                        sql,
                        lambda: mcp_query(
                            self.client,
                            sql,
                            purpose,
                            trace=execution_trace,
                        ),
                    )

                if not (
                    context_action
                    and context_action.get("kind") == "document_corroboration"
                ):
                    result = await extend(result, reader, state)

                from agent.document_corroboration import corroborate
                from agent.phase4b1_semantic_playground import call

                async def search(query):
                    return await call(
                        self.client,
                        "search_knowledge",
                        {
                            "query": query,
                            "top_k": 5,
                            "trust_level": "internal",
                        },
                        trace=execution_trace,
                    )

                query = question

                if (
                    context_action
                    and context_action.get("kind") == "document_corroboration"
                ):
                    query = (
                        result["database_record"]["question"]
                        + "; cross-check documents"
                    )

                result = await corroborate(
                    query,
                    result,
                    search,
                    state,
                )

            except Exception as exc:
                # Preserve the existing governed failure semantics.
                # Retained proofs do not certify an incomplete investigation.
                failure = {
                    "route": "investigation",
                    "status": "EXECUTION_FAILED",
                    "executable": False,
                    "causal_claim": False,
                    "validated_evidence": archive,
                    "execution_trace": execution_trace,
                    "model_calls": models,
                    "orchestration": state.snapshot(
                        "INITIAL_EXECUTION_FAILED"
                    ),
                    "limitations": [
                        "Execution failed; retained steps do not certify "
                        "the complete requested investigation"
                    ],
                }

                failure = await explain_result(
                    question,
                    failure,
                    None,
                )

                exc.investigation_record = canonical_result(
                    question,
                    failure,
                )
                raise

            # Stage 1: Existing deterministic / selector explanation.
            # This preserves all original governed evidence and templates.
            result = await explain_result(
                question,
                {
                    **result,
                    "validated_evidence": archive,
                },
                self.explanation_client,
            )

            # Stage 2: Optional business reasoning v3.
            #
            # This is the previously commented-out integration.
            # It is now enabled, exactly once.
            #
            # IMPORTANT:
            # Gemini explanation failure must never turn a completed
            # investigation into an EXECUTION_FAILED result.
            try:
                result = await add_business_reasoning(
                    question,
                    result,
                    self.explanation_client,
                    timeout_seconds=12,
                )
            except Exception as exc:
                result = {
                    **result,
                    "business_reasoning_status": "INTEGRATION_FAILED",
                    "business_reasoning_error_type": type(exc).__name__,
                }

            final_result = {
                **result,
                "execution_trace": execution_trace,
                "validated_evidence": archive,
                "model_calls": models,
            }

            # Stage 5.13L: explicitly opted-in completion coverage.
            # No additional tools, replanning, or evidence mutation.
            import os
            if os.environ.get("OPSLENS_COVERAGE_STOP_GATE") == "1":
                from agent.coverage_stop_gate import apply_gate
                final_result = apply_gate(question, final_result)

            return final_result

    async def _investigate(
        self,
        question,
        *,
        cohort_audit=None,
        execution_trace,
        context_action=None,
        state=None,
    ):
        from agent.phase4b1_semantic_playground import call

        # Security guidance is a non-executable, deterministic capability.
        # It never interprets a vendor note as an authorized instruction.
        if context_action is None:
            from agent.security_guidance import security_guidance
            security_result = security_guidance(question)
            if security_result is not None:
                return security_result

        if (
            context_action
            and context_action.get("kind") == "document_corroboration"
        ):
            from copy import deepcopy

            record = context_action["record"]
            original = record["payload"].get("database_record", record)

            result = deepcopy(original["payload"])
            result["database_record"] = deepcopy(original)

            prior = record["payload"]
            history = deepcopy(prior.get("document_check_history", []))

            if len(history) >= 3:
                result = deepcopy(prior)
                result["document_history_limit_reached"] = True
                result["document_evidence"].setdefault(
                    "retained_execution_trace",
                    deepcopy(prior.get("execution_trace", [])),
                )
                return result

            if prior.get("document_evidence"):
                history.append({
                    "document_evidence": deepcopy(
                        prior["document_evidence"]
                    ),
                    "execution_trace": deepcopy(
                        prior.get("execution_trace", [])
                    ),
                })

            if history:
                result["document_check_history"] = history

            return result

        async def finance_reader(sql, purpose):
            if state is not None:
                return await state.read(
                    sql,
                    lambda: mcp_query(
                        self.client,
                        sql,
                        purpose,
                        trace=execution_trace,
                    ),
                )

            return await mcp_query(
                self.client,
                sql,
                purpose,
                trace=execution_trace,
            )

        async def graph_reader(sql, request, plan):
            from agent.phase4b1_semantic_playground import call

            args = {
                "query": sql,
                "purpose": "Governed semantic graph analysis",
                "expected_grain": (
                    "grouped by " + ",".join(request.dimensions)
                    if request.dimensions
                    else "one aggregate"
                ),
                "max_rows": request.limit,
                "timeout_ms": 20000,
            }

            if state is not None:
                return await state.read(
                    "graph:" + sql,
                    lambda: call(
                        self.client,
                        "run_readonly_sql",
                        args,
                        trace=execution_trace,
                    ),
                )

            return await call(
                self.client,
                "run_readonly_sql",
                args,
                trace=execution_trace,
            )

        from agent.refund_routing import contextual as refund_context
        from agent.session_context import safe

        refund = (
            refund_context(question, {}, {})
            if context_action is None and safe(question)
            else None
        )

        if refund is not None:
            context_action, immediate, _ = refund
            if immediate:
                return immediate

        if (
            context_action is not None
            and context_action.get("kind") == "refund_concentration"
        ):
            from agent.refund_action_policy import evaluate as refund_policy

            policy = refund_policy(question, context_action)

            if policy["decision"] != "SEMANTIC_MATCH_SHADOW":
                return {
                    "route": "refund_action_policy",
                    "status": "NEEDS_CLARIFICATION",
                    "executable": False,
                    "causal_claim": False,
                    "reason": (
                        "The requested refund operation does not match "
                        "a verified supported question."
                    ),
                    "policy_decision": policy["decision"],
                }

            from agent.refund_concentration import initial

            result = await initial(
                context_action["start"],
                context_action["end"],
                finance_reader,
            )
            result["refund_intent"] = context_action["detail"]
            return result

        from agent.seller_routing import contextual as seller_context
        from agent.session_context import safe

        seller = (
            seller_context(question, {}, {})
            if context_action is None and safe(question)
            else None
        )

        if seller is not None:
            context_action, immediate, _ = seller
            if immediate:
                return {
                    **immediate,
                    "execution_trace": execution_trace,
                }

        if (
            context_action is not None
            and context_action.get("kind") == "seller_concentration"
        ):
            from agent.seller_concentration import initial

            response = await initial(
                context_action["start"],
                context_action["end"],
                finance_reader,
            )

            return {
                **response,
                "execution_trace": execution_trace,
            }

        if (
            context_action is not None
            and context_action.get("kind") == "delivery_review_comparison"
        ):
            from agent.delivery_review_comparison import investigate

            response = await investigate(
                context_action["start"],
                context_action["end"],
                finance_reader,
            )

            return {
                **response,
                "execution_trace": execution_trace,
            }

        from agent.delivery_review_routing import (
            route as delivery_review_route,
        )

        comparison = await delivery_review_route(
            question,
            finance_reader,
        )

        if comparison is not None:
            return {
                **comparison,
                "execution_trace": execution_trace,
            }

        if (
            context_action is not None
            and context_action.get("kind") == "recovery"
        ):
            response = await self.session.recovery.dispatch(
                question,
                prior_dispatch,
                self.router,
                self.finance,
                finance_reader,
                self.graph,
                self.planner,
                graph_reader,
                self.investigation,
            )

            return {
                **response,
                "execution_trace": execution_trace,
            }

        if context_action is not None:
            from agent.phase4b57_nl_dynamic_finance import execute
            from agent.phase4b56_dynamic_period import requested_period
            from agent.session_context import METRICS

            if (
                context_action.get("kind") != "finance"
                or context_action.get("metric") not in METRICS.values()
            ):
                raise ValueError("Unsupported contextual capability")

            before = (
                requested_period(*context_action["before"])
                if context_action.get("before")
                else None
            )

            after = requested_period(*context_action["after"])

            evidence = await execute(
                context_action["metric"],
                before,
                after,
                finance_reader,
            )

            self.session.recovery.remember_finance(
                context_action["metric"],
                after.start,
                after.end,
                "finance_compare" if before else "finance_measure",
            )

            return {
                "route": (
                    "finance_compare" if before else "finance_measure"
                ),
                "status": evidence["status"],
                "executable": True,
                "causal_claim": False,
                "evidence": evidence,
                "execution_trace": execution_trace,
            }

        async def existing_dispatch():
            if not self.session.gemini_enabled:
                try:
                    return await self.session.dispatch(
                        question,
                        prior_dispatch,
                        self.router,
                        self.finance,
                        finance_reader,
                        self.graph,
                        self.planner,
                        graph_reader,
                        self.investigation,
                    )
                except ModelDisabled:
                    return route_result(
                        "NOT_INTERPRETED",
                        "No deterministic route resolved this question.",
                    )

            # Speculate only on a copy. Rejected parsing must not
            # mutate the session.
            from copy import deepcopy

            recovery = deepcopy(self.session.recovery)
            disabled = DisabledInterpreter()

            try:
                response = await recovery.dispatch(
                    question,
                    prior_dispatch,
                    disabled,
                    disabled,
                    finance_reader,
                    disabled,
                    self.planner,
                    graph_reader,
                    disabled,
                )
            except ModelDisabled:
                return route_result(
                    "NOT_INTERPRETED",
                    "No deterministic route resolved this question.",
                )

            # Preserve the session-owned recovery object identity.
            self.session.recovery.__dict__.clear()
            self.session.recovery.__dict__.update(
                recovery.__dict__
            )

            return response

        async def existing_finance_investigator(q, reader):
            from agent.phase4c6_nl_investigation import (
                CompiledComparisonInterpreter,
            )

            interpreter = CompiledComparisonInterpreter()

            return await adaptive_investigation(
                q,
                interpreter,
                reader,
            )

        response = await multi_domain_route(
            question,
            existing_dispatch,
            finance_reader,
            existing_finance_investigator,
            cohort_audit=(
                self.cohort_audit
                if cohort_audit is None
                else cohort_audit
            ),
        )

        response = await repair_incident(
            question,
            response,
            existing_finance_investigator,
            finance_reader,
        )

        # Existing scalar and ranking NL routes still receive a
        # validated interpreter when deterministic parsing fails.
        import re

        unresolved_scalar = (
            response.get("status") == "ACTIONABLE_EVIDENCE_GAP"
            and re.match(
                r"\s*(?:what|how much|how many|compare|rank|"
                r"show|list|top)\b",
                question,
                re.I,
            )
            and not re.search(
                r"\b(?:why|cause\w*|investigat\w*|"
                r"explain|driver\w*|stockout\w*|mix|"
                r"supplier|campaign|accrual|invoice|"
                r"confound\w*)\b",
                question,
                re.I,
            )
        )

        should_use_model = (
            (
                response.get("route") == "unified_interpreter"
                and response.get("status") == "NOT_INTERPRETED"
            )
            or unresolved_scalar
        )

        if should_use_model and self.session.gemini_enabled:
            fallback = response

            try:
                response = await self.session.dispatch(
                    question,
                    prior_dispatch,
                    self.router,
                    self.finance,
                    finance_reader,
                    self.graph,
                    self.planner,
                    graph_reader,
                    self.investigation,
                    deterministic_fallback=existing_dispatch,
                )

                if response.get("provider_fallback"):
                    response = {
                        **fallback,
                        "provider_fallback": response["provider_fallback"],
                    }

            except Exception as exc:
                response = {
                    **fallback,
                    "provider_fallback": {
                        "status": "UNAVAILABLE",
                        "error_type": type(exc).__name__,
                    },
                }

            response = await repair_incident(
                question,
                response,
                existing_finance_investigator,
                finance_reader,
            )

        return {
            **response,
            "execution_trace": execution_trace,
        }


def new_recovery_session():
    return RecoverySession(
        LanguageSession(
            ProductNLPSession(
                DeliveryComparisonSession(
                    UnifiedContext()
                )
            )
        )
    )


async def open_investigation_runtime(*, gemini_enabled=True):
    """Create existing components within the governed MCP context."""

    from mcp import Client
    from mcp_server.server import mcp

    recovery = new_recovery_session()

    session = UnifiedSession(
        recovery,
        gemini_client if gemini_enabled else None,
        gemini_enabled=gemini_enabled,
    )

    planner = GraphPlanner(
        Path(__file__).resolve().parents[1]
        / "reports/phase4b42_relationship_audit.json"
    )

    components = [
        factory() if gemini_enabled else DisabledInterpreter()
        for factory in (
            GeminiRouter,
            Interpreter,
            GeminiSemanticInterpreter,
            GeminiInvestigationInterpreter,
        )
    ]

    client = Client(mcp)
    await client.__aenter__()

    return (
        InvestigationRuntime(
            client,
            session,
            *components,
            planner,
            None,
            gemini_client if gemini_enabled else None,
        ),
        client,
    )


async def main():
    parser = argparse.ArgumentParser()

    parser.add_argument(
        "--gemini",
        action="store_true",
        help="Opt-in to Gemini interpretation for new questions",
    )

    parser.add_argument(
        "--cohort-audit",
        type=Path,
        default=None,
        help="Optional validated raw Phase 5.2D cohort audit JSON",
    )

    flags = parser.parse_args()

    cohort_audit = (
        load_audit(flags.cohort_audit)
        if flags.cohort_audit
        else None
    )

    recovery = new_recovery_session()

    session = UnifiedSession(
        recovery,
        gemini_client if flags.gemini else None,
        gemini_enabled=flags.gemini,
    )

    router, finance, graph, investigation = [
        factory() if flags.gemini else DisabledInterpreter()
        for factory in (
            GeminiRouter,
            Interpreter,
            GeminiSemanticInterpreter,
            GeminiInvestigationInterpreter,
        )
    ]

    planner = GraphPlanner(
        Path(__file__).resolve().parents[1]
        / "reports/phase4b42_relationship_audit.json"
    )

    from mcp import Client
    from mcp_server.server import mcp
    from agent.phase4b1_semantic_playground import call

    async with Client(mcp) as client:

        async def finance_reader(sql, purpose):
            return await mcp_query(
                client,
                sql,
                purpose,
            )

        async def graph_reader(sql, request, plan):
            return await call(
                client,
                "run_readonly_sql",
                {
                    "query": sql,
                    "purpose": "Governed semantic graph analysis",
                    "expected_grain": (
                        "grouped by " + ",".join(request.dimensions)
                        if request.dimensions
                        else "one aggregate"
                    ),
                    "max_rows": request.limit,
                    "timeout_ms": 20000,
                },
            )

        print(
            "OpsLens 5.1 unified CLI | "
            + (
                "Gemini interpretation ON"
                if flags.gemini
                else "deterministic-only"
            )
            + " | exit to quit"
        )

        while True:
            try:
                q = input("\nOpsLens > ").strip()
            except (EOFError, KeyboardInterrupt):
                break

            if q.lower() in ("exit", "quit"):
                break

            if not q:
                continue

            try:

                async def existing_dispatch():
                    try:
                        return await session.dispatch(
                            q,
                            prior_dispatch,
                            router,
                            finance,
                            finance_reader,
                            graph,
                            planner,
                            graph_reader,
                            investigation,
                        )
                    except ModelDisabled:
                        return route_result(
                            "NOT_INTERPRETED",
                            "Model interpretation is disabled. "
                            "This route returned no measurements.",
                        )

                async def existing_finance_investigator(
                    question,
                    rd,
                ):
                    from agent.phase4c6_nl_investigation import (
                        CompiledComparisonInterpreter,
                    )

                    return await adaptive_investigation(
                        question,
                        CompiledComparisonInterpreter(),
                        rd,
                    )

                response = await multi_domain_route(
                    q,
                    existing_dispatch,
                    finance_reader,
                    existing_finance_investigator,
                    cohort_audit=cohort_audit,
                )

                response = await repair_incident(
                    q,
                    response,
                    existing_finance_investigator,
                    finance_reader,
                )

                print(
                    json.dumps(
                        response,
                        indent=2,
                        default=str,
                        ensure_ascii=False,
                    )
                )

            except Exception as exc:
                while (
                    isinstance(exc, BaseExceptionGroup)
                    and exc.exceptions
                ):
                    exc = exc.exceptions[0]

                print(
                    "BLOCKED:",
                    type(exc).__name__,
                    str(exc)[:450],
                )


if __name__ == "__main__":
    asyncio.run(main())
