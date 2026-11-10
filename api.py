"""Local API adapter for the existing bounded OpsLens investigator."""
from __future__ import annotations

import json
import asyncio
import logging
import os
import secrets
import re
import time
import sqlite3
from copy import deepcopy
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException, Query, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from fastapi.responses import JSONResponse
from starlette.concurrency import run_in_threadpool

ROOT = Path(__file__).resolve().parent
from dotenv import load_dotenv
from frontend_origins import configured_frontend_origins

# Load local configuration before installing either browser security boundary.
# Explicit process environment always takes precedence.
load_dotenv(ROOT / '.env', override=False)
FRONTEND_ORIGINS = configured_frontend_origins()
logger = logging.getLogger("opslens.api")
app = FastAPI(title="OpsLens local API", version="0.1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=list(FRONTEND_ORIGINS),
    allow_methods=["GET", "POST", "DELETE"],
    allow_headers=["Content-Type"],
    allow_credentials=True,
)
from investigation_sessions import SessionStore, COOKIE
sessions = SessionStore()
from investigation_traces import TraceStore, annotate
traces = TraceStore()


@app.middleware('http')
async def session_origin_boundary(request: Request, call_next):
    if request.method in ('POST','DELETE') and request.url.path.startswith(('/api/investigation-sessions','/api/investigations')):
        origin = request.headers.get('origin')
        if (origin is not None and origin not in FRONTEND_ORIGINS) or request.headers.get('sec-fetch-site', '').lower() == 'cross-site':
            return JSONResponse(status_code=403,content={'detail':'Untrusted request origin'})
    response = await call_next(request)
    if request.url.path.startswith(('/api/investigation-sessions','/api/investigations')):
        response.headers['Cache-Control'] = 'no-store'
    return response


@app.post('/api/investigation-sessions')
async def create_investigation_session(request: Request, response: Response):
    owner = request.cookies.get(COOKIE,'')
    if not re.fullmatch(r'[A-Za-z0-9_-]{43}',owner): owner = secrets.token_urlsafe(32)
    entry = sessions.create(owner)
    response.set_cookie(COOKIE,owner,httponly=True,samesite='strict',
        secure=request.url.scheme=='https' or os.getenv('OPSLENS_COOKIE_SECURE')=='1',path='/api')
    return {'session':sessions.snapshot(entry)}


@app.get('/api/investigation-sessions/{session_id}')
async def get_investigation_session(session_id: str, request: Request):
    entry = sessions.acquire(session_id,request.cookies.get(COOKIE))
    try: return {'session':sessions.snapshot(entry)}
    finally: entry.lock.release()


@app.delete('/api/investigation-sessions/{session_id}')
async def delete_investigation_session(session_id: str, request: Request):
    entry = sessions.acquire(session_id,request.cookies.get(COOKIE))
    try:
        try:traces.delete(entry.id,entry.owner)
        except (OSError,sqlite3.Error):logger.warning('Trace purge unavailable; session access is revoked by reset')
        sessions.delete(entry)
        return {'status':'RESET'}
    finally: entry.lock.release()


@app.get('/api/investigation-sessions/{session_id}/runs/{run_id}/replay')
async def replay_investigation(session_id: str, run_id: str, request: Request):
    entry=sessions.acquire(session_id,request.cookies.get(COOKIE))
    try:
        try:return traces.load(entry.id,entry.owner,run_id)
        except KeyError:raise HTTPException(404,'Saved run unavailable or expired')
        except (ValueError,OSError,sqlite3.Error) as exc:raise HTTPException(503,'Saved run failed integrity or storage checks') from exc
    finally:entry.lock.release()


@app.exception_handler(Exception)
async def unexpected_error(request: Request, exc: Exception):
    logger.exception("Unhandled API error for %s %s", request.method, request.url.path)
    return JSONResponse(status_code=500, content={"detail": {"status": "INTERNAL_ERROR", "reason": "The local API could not complete this request. Check backend logs for the traceback."}})


class InvestigationRequest(BaseModel):
    question: str = Field(min_length=1, max_length=500)
    session_id: str | None = Field(default=None,pattern=r'^[A-Za-z0-9_-]{43}$')
    revision: int | None = Field(default=None,ge=0,strict=True)


def _report(name: str) -> Any:
    try:
        return json.loads((ROOT / "reports" / name).read_text(encoding="utf-8"))
    except FileNotFoundError:
        logger.warning("Saved evaluation report is missing: %s", ROOT / "reports" / name)
        return None
    except (OSError, json.JSONDecodeError):
        logger.exception("Could not read saved evaluation report: %s", ROOT / "reports" / name)
        return None


def _metric_definitions(domain: str | None = None) -> list[dict[str, Any]]:
    catalog = json.loads((ROOT / "config" / "metric_catalog.json").read_text(encoding="utf-8"))
    definitions = catalog.get("metrics", [])
    if domain:
        definitions = [item for item in definitions if item.get("domain", "").lower() == domain.strip().lower()]
    return definitions


def _cohort_artifacts():
    from scripts.phase5_2d_assess import assess as assess_2d
    from scripts.phase5_2b_assess import assess as assess_2b

    for filename, assessor in (("phase5_2d_cohort_audit.json", assess_2d), ("phase5_2b_cohort_audit.json", assess_2b)):
        try:
            payload = json.loads((ROOT / filename).read_text(encoding="utf-8-sig"))
            checked = assessor(payload)
        except (OSError, ValueError, TypeError):
            logger.warning("Cohort audit unavailable or invalid: %s", filename)
            continue
        yield filename, payload, checked


def _validated_cohort_audits() -> list[dict[str, Any]]:
    return [{
        "artifact": filename,
        "contract": payload.get("contract"),
        "time_basis": payload.get("time_basis"),
        "status": checked.get("status"),
        "months": checked.get("months", []),
        "failures": checked.get("failures", []),
        "causal_claim": False,
        "approved_for_mcp": False,
        "scope": "delivery and review cohort reconciliation only",
    } for filename, payload, checked in _cohort_artifacts()]


@app.get("/api/health")
async def health():
    return {"status": "ok", "service": "opslens-local-api"}


@app.get("/api/ready", responses={503: {"description": "Runtime dependency or role policy unavailable"}})
async def ready():
    try:
        from mcp_server.readiness import inspect_runtime
        report = await asyncio.wait_for(run_in_threadpool(inspect_runtime), timeout=8)
    except Exception as exc:
        logger.warning("Readiness probe failed (%s)", type(exc).__name__)
        report = {"status": "NOT_READY", "reason": "Runtime verification unavailable"}
    return JSONResponse(report, status_code=200 if report["status"] == "READY" else 503)


@app.get("/api/overview")
async def overview():
    report_name = "phase5_3f_pre_ui_review.json"
    review = _report(report_name) or {}
    incidents = review.get("incidents", {})
    core = review.get("core", {}).get("observed_score", {})
    incident_score = incidents.get("observed_score", {})
    return {
        "evaluation_scope": "Saved finite evaluation runs; not production certification",
        "core": {"passed": core.get("passed"), "total": core.get("total")},
        "incident_coverage": incidents.get("coverage_counts", {}),
        "incident_safety": {"passed": incident_score.get("safety_passed"), "total": incident_score.get("safety_total")},
        "open_gates": review.get("open_gates", []),
        "acceptance_approved": review.get("ui_design_scope", {}).get("implementation_acceptance_approved", False),
        "reports_available": bool(review),
        "report_name": report_name,
        "report_status": review.get("review_status") if review else None,
    }


@app.get("/api/metrics")
async def metrics(domain: str | None = None):
    try:
        definitions = _metric_definitions(domain)
        return {"metrics": definitions, "meta": {"count": len(definitions), "source": "config/metric_catalog.json"}, "source": "governed_metric_catalog", "execution_capabilities": _execution_capabilities()}
    except (OSError, json.JSONDecodeError) as exc:
        raise HTTPException(status_code=503, detail="Governed metric catalog is unavailable") from exc


def _execution_capabilities() -> list[dict[str, Any]]:
    """Report registered app-owned compilers; registration is not live data proof."""
    from agent.phase4b2_metric_governance import METRICS as finance_metrics
    from agent.phase4c11_satisfaction import METRICS as satisfaction_metrics, SOURCE as satisfaction_source
    from agent.phase4c15_delivery import METRICS as delivery_metrics, SOURCE as delivery_source
    from agent.phase4c19_product import METRICS as product_metrics, SOURCE as product_source
    from dashboard_api import FINANCE_METRICS

    return [
        {"name": "Home monthly comparison", "route": "/api/dashboard", "state": "REGISTERED_GOVERNED_PATH", "metric_ids": [*FINANCE_METRICS, "late_delivery_rate", "average_review_score"], "sources": list(dict.fromkeys([finance_metrics[key].source for key in FINANCE_METRICS] + [delivery_source, satisfaction_source]))},
        {"name": "Finance metric compiler", "route": "Investigation runtime", "state": "REGISTERED_GOVERNED_PATH", "metric_ids": sorted(finance_metrics), "sources": sorted({item.source for item in finance_metrics.values()})},
        {"name": "Delivery metric compiler", "route": "Investigation runtime", "state": "REGISTERED_GOVERNED_PATH", "metric_ids": sorted(delivery_metrics), "sources": [delivery_source]},
        {"name": "Satisfaction metric compiler", "route": "Investigation runtime", "state": "REGISTERED_GOVERNED_PATH", "metric_ids": sorted(satisfaction_metrics), "sources": [satisfaction_source]},
        {"name": "Product/category item metric compiler", "route": "Investigation runtime", "state": "REGISTERED_GOVERNED_PATH", "metric_ids": sorted(product_metrics), "sources": [product_source]},
    ]


@app.get("/api/evidence")
async def evidence():
    """Expose approved metric provenance and validated cohort audit summaries only."""
    try:
        audits = _validated_cohort_audits()
        return {
            "metrics": _metric_definitions(),
            "cohort_audits": audits,
            "limitations": [
                "Metric definitions are governed catalog metadata; presence here does not mean every metric has a live execution route.",
                "Cohort audits reconcile delivery and review order populations only; they do not establish finance population equality or causation.",
                "No document retrieval or general source browser is exposed by this endpoint.",
            ],
        }
    except (OSError, json.JSONDecodeError) as exc:
        raise HTTPException(status_code=503, detail="Governed evidence metadata is unavailable") from exc


@app.get("/api/dashboard")
async def business_dashboard(month: str = Query(default="2018-06", pattern=r"^20\d{2}-(0[1-9]|1[0-2])$")):
    """Read only monthly KPI comparison over already governed metric compilers."""
    from dashboard_api import load_dashboard

    try:
        return await load_dashboard(month)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except Exception as exc:
        logger.exception("Dashboard retrieval failed for month %s", month)
        while isinstance(exc, BaseExceptionGroup) and exc.exceptions:
            exc = exc.exceptions[0]
        raise HTTPException(status_code=503, detail={
            "status": "DASHBOARD_UNAVAILABLE",
            "reason": "Governed dashboard readings could not be retrieved. Check MCP and PostgreSQL availability.",
        }) from exc


_canonical_schema = json.loads((ROOT / "config/investigation_result.schema.json").read_text(encoding="utf-8"))
_investigation_http = {
    200: {"description": "Investigation including clarification and partial evidence", "content": {"application/json": {
        "schema": {"type": "object", "required": ["canonical_result", "result"], "additionalProperties": True,
                   "properties": {"canonical_result": _canonical_schema, "result": {"type": "object"},
                                  "session": {"type": "object"}}}}}},
    **{code: {"description": label, "content": {"application/json": {"schema": {
        "type": "object", "required": ["detail"], "properties": {"detail": {"oneOf": [
            {"type": "string"}, {"type": "array"}, {"type": "object", "additionalProperties": True,
             "properties": {"canonical_result": _canonical_schema, "session": {"type": "object"}}}]}}}}}}
       for code, label in ((403, "Origin rejected"), (404, "Expired or unknown session"),
                           (409, "Revision or concurrent turn conflict"), (413, "Session storage limit"),
                           (422, "Invalid request"), (503, "Investigation unavailable"))},
}


@app.post("/api/investigations", responses=_investigation_http)
async def investigate(request: InvestigationRequest, http_request: Request):
    started=time.monotonic()
    if request.session_id is None:
        return await _execute_investigation(request)
    if request.revision is None:
        raise HTTPException(422,'Session turns require the last observed revision')
    from scripts.phase5_1_playground import new_recovery_session
    from agent.session_context import resolve, safe
    from agent.investigation_result import investigation_response
    entry = sessions.acquire(request.session_id,http_request.cookies.get(COOKIE),request.revision)
    try:
        recovery = deepcopy(entry.recovery) if entry.recovery else new_recovery_session()
        # Capture server-owned pending context before resolution mutates it.
        refund_pending_before = deepcopy(recovery.investigation_pending)
        canonical, action, immediate, provenance = resolve(request.question,recovery,entry.last_valid)

        # A contextual refund action must reconstruct to an explicit,
        # independently routable operation before entering the runtime.
        if isinstance(action, dict) and action.get("kind") == "refund_concentration":
            from agent.refund_action_policy import evaluate as refund_policy
            original_policy = refund_policy(request.question, action)

            if original_policy["decision"] != "SEMANTIC_MATCH_SHADOW":
                from agent.refund_context_binding import assess as bind_refund_context
                from agent.refund_routing import contextual as reroute_refund

                binding = bind_refund_context(
                    request.question,
                    action,
                    prior=entry.last_valid,
                    pending=refund_pending_before,
                )

                verified = False
                if binding["status"] == "CONTEXT_SEMANTIC_MATCH_SHADOW":
                    proposed = binding["canonical_question"]
                    routed = reroute_refund(proposed, {}, {})

                    if routed is not None:
                        routed_action, routed_immediate, _ = routed
                        verified = (
                            routed_immediate is None
                            and type(routed_action) is dict
                            and routed_action == action
                            and refund_policy(proposed, routed_action)["decision"]
                            == "SEMANTIC_MATCH_SHADOW"
                        )

                    if verified:
                        canonical = proposed
                        action = routed_action
                        provenance["resolved_question"] = proposed
                        provenance["context_metric_binding"] = binding["requested_metric"]

                if not verified:
                    action = None
                    immediate = {
                        "route": "refund_action_policy",
                        "status": "NEEDS_CLARIFICATION",
                        "executable": False,
                        "causal_claim": False,
                        "reason": (
                            "The requested refund operation could not be "
                            "verified from the available session context."
                        ),
                    }
        provenance['source_turn'] = entry.last_valid_turn
        provenance['session_id'] = entry.id
        provenance['pending_source_turn'] = entry.recovery.investigation_pending.get('source_turn') if entry.recovery and entry.recovery.investigation_pending else None
        error = None
        try:
            # Existing Gemini adapters are synchronous. Keep them off the ASGI
            # loop; the runtime and MCP client are opened/closed in one worker loop.
            # Starlette waits for worker completion on cancellation, retaining the
            # session lock until its isolated state can no longer be mutated.
            body = investigation_response(request.question,immediate) if immediate is not None else await run_in_threadpool(
                lambda: asyncio.run(_execute_investigation(request.model_copy(update={'question':canonical}),
                    recovery=recovery, context_action=action)))
        except HTTPException as exc:
            error = exc
            record = exc.detail.get('canonical_result') if isinstance(exc.detail,dict) else None
            if not record: raise
            body = {'canonical_result':record,'result':record['payload']}
        # Canonical result records the actual user message and its explicit context sources.
        result = body['canonical_result']['payload']
        result['context_provenance'] = provenance
        # Enrich the existing canonical record without reserializing transported
        # numbers: decimal/integer encoding metadata belongs to this record.
        body['canonical_result']['question'] = request.question
        body['question'] = request.question
        body['result'] = result
        validated = (result.get('executable') is True and result.get('causal_claim') is False
            and result.get('status') in {'MEASURED_WITH_SCOPE_LIMITS','MEASURED_WITH_LIMITATIONS','COMPARISON_MEASURED_WITH_SCOPE_LIMITS',
                'EVIDENCE_RANKED_NOT_CAUSAL','PREMISE_NOT_CONFIRMED','DESCRIPTIVE_DECOMPOSITION_ONLY','THREE_DOMAIN_DESCRIPTIVE_EVIDENCE',
                'CROSS_DOMAIN_DESCRIPTIVE_COMPARISON','PARTIAL_GOVERNED_EVIDENCE','PARTIAL_EVIDENCE_BUDGET','INSUFFICIENT_GOVERNED_EVIDENCE'})
        clarify = error is None and safe(request.question) and result.get('status') in ('NEEDS_CLARIFICATION','CANCELLED')
        if clarify and recovery.investigation_pending:
            recovery.investigation_pending['source_turn'] = entry.revision+1
            result['clarification_context'] = deepcopy(recovery.investigation_pending)
        body['canonical_result']=annotate(body['canonical_result'],time.monotonic()-started,validated)
        body['result']=body['canonical_result']['payload']
        try:
            traces.save(entry.id,entry.owner,body['canonical_result'])
        except Exception:
            # Audit storage must not discard completed analytical findings.
            body['result']['observability']['persistence']='UNAVAILABLE'
            logger.warning('Investigation trace persistence unavailable')
        try:
            sessions.commit(entry,body['canonical_result'],recovery,validated=validated,clarify=clarify)
        except HTTPException as storage_error:
            from agent.investigation_result import canonical_result
            raise HTTPException(storage_error.status_code,{'reason':str(storage_error.detail),
                'canonical_result':canonical_result(request.question,{
                    'route':'session_context','status':'EXECUTION_FAILED','executable':False,'causal_claim':False,
                    'completed_result':body['canonical_result'],'limitations':['Result was not committed: session storage limit reached; previous validated context remains active']}),
                'session':sessions.snapshot(entry)}) from storage_error
        snapshot = sessions.snapshot(entry)
        body['session'] = snapshot
        if error:
            raise HTTPException(error.status_code,{**error.detail,'canonical_result':body['canonical_result'],'session':snapshot})
        return body
    finally: entry.lock.release()


async def _execute_investigation(request: InvestigationRequest, *, recovery=None, context_action=None):
    """Run through the same Phase 5.1/5.2E/5.3C routes used by the unified CLI."""
    response = None
    try:
        from scripts.phase5_1_playground import open_investigation_runtime

        audit = _cohort_audit_for(request.question)

        gemini_enabled = bool(os.getenv("GOOGLE_API_KEY") or os.getenv("GEMINI_API_KEY"))
        runtime, client = await open_investigation_runtime(gemini_enabled=gemini_enabled)
        if recovery is not None: runtime.session.recovery = recovery
        try:
            response = await runtime.investigate(request.question, cohort_audit=audit,
                **({'context_action':context_action} if context_action is not None else {}))
        finally:
            await client.__aexit__(None, None, None)
        from agent.investigation_result import investigation_response
        return investigation_response(request.question, response)
    except Exception as exc:
        logger.warning("Investigation request failed (%s)",type(exc).__name__)
        record = getattr(exc, 'investigation_record', None) or getattr(exc.__context__, 'investigation_record', None)
        if record is None and isinstance(response, dict):
            from agent.investigation_result import canonical_result
            record = canonical_result(request.question, {
                'route':'investigation', 'status':'EXECUTION_FAILED', 'executable':False, 'causal_claim':False,
                'completed_result':response,
                'limitations':['Service cleanup failed after execution; the completed result is retained separately'],
            })
        if record is None:
            from agent.investigation_result import canonical_result
            record=canonical_result(request.question,{'status':'EXECUTION_FAILED','executable':False,'causal_claim':False,
                'error_type':type(exc).__name__,'limitations':['No completed validated findings were returned.']})
        while isinstance(exc, BaseExceptionGroup) and exc.exceptions:
            exc = exc.exceptions[0]
        raise HTTPException(
            status_code=503,
            detail={"status": "INVESTIGATION_UNAVAILABLE", "error_type": type(exc).__name__, "reason": "The governed investigation service could not complete this request. Check backend logs and local PostgreSQL/MCP availability.",
                    **({"canonical_result": record} if record is not None else {})},
        ) from exc


def _cohort_audit_for(question: str) -> dict[str, Any] | None:
    """Attach only a repository audit whose exact periods match this bounded request."""
    try:
        from agent.phase5_2c_three_domain import periods_of
        from agent.phase5_2e_multidomain_router import decision
        from scripts.phase5_2b_assess import DATES as may_june
        from scripts.phase5_2d_assess import DATES as february_march

        route = decision(question)
        if not route or route[0] != "execute":
            return None
        requested = periods_of(route[1])
        for dates, filename in ((february_march, "phase5_2d_cohort_audit.json"),
                                (may_june, "phase5_2b_cohort_audit.json")):
            if requested == [list(period) for period in dates]:
                # The runtime assessor must see (and reject) a tampered artifact.
                return json.loads((ROOT / filename).read_text(encoding="utf-8-sig"))
    except (OSError, json.JSONDecodeError, TypeError, ValueError, KeyError):
        return None
    return None
