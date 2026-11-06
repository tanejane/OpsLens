"""Loopback benchmark app. Construct outbound Gemini content from an independent allowlist."""
import hashlib
import json
import os
import re
import time
from contextvars import ContextVar
from pathlib import Path

from google import genai
from google.genai import types
from fastapi.responses import JSONResponse
from api import app
from agent.phase4c1_router import ROUTER_SCHEMA
from agent.phase4b57_nl_dynamic_finance import API_SCHEMA
from agent.phase4b44_gemini_interpreter import GEMINI_INTERPRETATION_SCHEMA
from agent.phase4c6_nl_investigation import SCHEMA
from agent.delivery_review_routing import PERIOD_SCHEMA
from agent.phase4c4_drivers import COMPONENTS
from agent.phase5_1_explanation import NARRATIVE_REFS
from scripts.phase5_3_eval import CASES
from scripts.phase5_3b_incident_eval import PROBES

QUESTIONS = {**{c.id:c.query for c in CASES}, **{p.key:p.prompt for p in PROBES}}
ACTIVE = ContextVar("benchmark_case", default=None)
# Digest the reviewed application instructions. Never forward caller-provided config or tool definitions.
TASKS = {
    "5fb726e96a88a999d09ff62ad0f1e68ccb7200c3efa877c574ef087b3dc95918": ("route", ROUTER_SCHEMA),
    "6b6148f971b4821ae74c2d7c26d4a7496a06a9dba4622e69c553d68c428894a3": ("finance", API_SCHEMA),
    "07d3cdc5068d722fa21efd0a32c66d01c5de49a8f4e950f001c8743f462f2670": ("semantic", GEMINI_INTERPRETATION_SCHEMA),
    "6608ddbb30517513b87d6f77c2f79cfe438e95e4f83c33fd00624fbb00b48d4d": ("finance_periods", SCHEMA),
    "11e9a9b535a7f0b571c6d76434a43c1bdb4b05f4eb128d400153140a804cbee7": ("intent", None),
    "8b9396259a2539d9bd3c072622a437cb01b5f88eb2fd3e5243cb044964fa07f6": ("explanation", None),
    "08ab27e51796d4129666d7a53c7025d59cdcf0ff4d52498466c19d2829a8bdf8": ("refund_period", PERIOD_SCHEMA),
    "b31be24dc704083bcb9e7aa2bb51f8562d4ca89b42925954899b5ca0fa85b2f6": ("seller_period", PERIOD_SCHEMA),
    "927c5735ff43477cca2e46241685aef8d79f8fef8cb343650bcab233a70450ac": ("delivery_period", PERIOD_SCHEMA),
}
REFS = {
    **{key:set(refs) for key,refs in NARRATIVE_REFS.items()},
    "finance_divergence": {"premise."+k for k in ("divergence_confirmed","revenue_delta","contribution_profit_delta")},
    "product_gmv": {"evidence."+k for k in ("metric_id","value","category","period","source")},
    "cost_per_order_context": {"order_normalized_evidence.status"} |
        {"order_normalized_evidence.components."+k+".change_per_order" for k in COMPONENTS},
    "measured_metrics": {f"observations.{i}.{k}" for i in range(12) for k in ("metric_id","value")},
    "period_comparison": {f"{group}.{metric}.{k}" for group in ("operational_changes","metric_changes")
                          for metric in ("late_delivery_rate","average_review_score","low_rating_rate")
                          for k in ("before","after","delta")},
}


def content_for(case, task, original):
    question = QUESTIONS[case]
    if task != "explanation":
        return question
    envelope = json.loads(original.removeprefix("USER QUESTION (untrusted):\n"))
    candidates = envelope["available_explanations"]
    if not isinstance(candidates, dict) or not all(
        name in REFS and isinstance(refs,list) and all(ref in REFS[name] for ref in refs)
        for name,refs in candidates.items()
    ):
        raise ValueError("Unapproved explanation references")
    return json.dumps({"question":question,"available_explanations":candidates})


def event(**fields):
    with Path(os.environ["OPSLENS_BENCHMARK_AUDIT"]).open("a",encoding="utf-8") as f:
        f.write(json.dumps(fields)+"\n")


_client = genai.Client
_stopped = False


class ScopedClient:
    def __init__(self, *, api_key, http_options=None):
        self.key = api_key
        self.models = self

    def generate_content(self, *, model, contents, config):
        global _stopped
        if _stopped:
            raise ValueError("Benchmark policy stop")
        case = ACTIVE.get()
        try:
            instruction = config.system_instruction
            task, schema = TASKS[hashlib.sha256(instruction.encode()).hexdigest()]
            if not re.fullmatch(r"gemini-[0-9][a-z0-9.-]{0,64}", model):
                raise ValueError("Unapproved model destination")
            body = content_for(case, task, contents)
        except Exception:
            _stopped = True
            event(case=case,status="POLICY_STOP")
            raise ValueError("Unapproved benchmark transmission") from None
        start = time.monotonic()
        status, code = "provider_error", None
        try:
            options = types.HttpOptions(base_url="https://generativelanguage.googleapis.com",
                timeout=12000, retry_options=types.HttpRetryOptions(attempts=1),
                client_args={"trust_env":False,"follow_redirects":False})
            with _client(api_key=self.key,vertexai=False,http_options=options) as provider:
                response = provider.models.generate_content(model=model, contents=body,
                    config=types.GenerateContentConfig(system_instruction=instruction,temperature=0,
                        response_mime_type="application/json",response_schema=schema,
                        automatic_function_calling=types.AutomaticFunctionCallingConfig(disable=True)))
            status = "returned"
            return response
        except Exception as exc:
            code = getattr(exc,"code",None)
            raise
        finally:
            event(case=case,task=task,model=model,status=status,code=code if isinstance(code,int) else None,
                  elapsed_ms=round((time.monotonic()-start)*1000),body_sha256=hashlib.sha256(body.encode()).hexdigest())


# This module is loaded only as the dedicated benchmark server.
genai.Client = ScopedClient


@app.middleware("http")
async def bind_fixed_case(request, call_next):
    if request.url.path != "/api/investigations":
        return await call_next(request)
    case = request.headers.get("x-opslens-benchmark-case")
    if case not in QUESTIONS or await request.json() != {"question":QUESTIONS[case]}:
        return JSONResponse({"detail":"Fixed benchmark cases only"},status_code=403)
    token = ACTIVE.set(case)
    try:
        return await call_next(request)
    finally:
        ACTIVE.reset(token)
