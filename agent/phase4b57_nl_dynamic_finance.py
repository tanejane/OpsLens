"""Phase 4B.5.7: constrained NL finance intent -> audited dynamic totals.

Never accepts LLM SQL, table names, dimensions, joins, or source permissions.
Failure/clarification never changes session context. Not causal investigation.
"""
from __future__ import annotations
import json, os, time, random
from dataclasses import dataclass
from decimal import Decimal
from typing import Literal
from pydantic import BaseModel, ConfigDict
from agent.phase4b54_governed_finance import METRICS, compare
from agent.phase4b56_dynamic_period import requested_period, audit_queries, audit_token, compile_metric, measurement_evidence

class Intent(BaseModel):
    model_config=ConfigDict(extra='forbid')
    intent: Literal['measure','compare','investigate','clarify']
    metric_id: str | None = None
    start_date: str | None = None
    end_date_exclusive: str | None = None
    comparison_start_date: str | None = None
    comparison_end_date_exclusive: str | None = None
    use_prior_metric: bool = False
    use_prior_period_as_comparison: bool = False
    ambiguity: str | None = None

@dataclass(frozen=True)
class Context:
    metric_id: str
    start_date: str
    end_date_exclusive: str

class Rejected(ValueError): pass
class ModelUnavailable(Rejected): pass
class ModelResponseInvalid(Rejected): pass
class NoSourceCoverage(Rejected): pass

def classify_model_error(exc):
    """Only retry transient transport/service failures; never retry grounding errors."""
    code=getattr(exc, 'code', None) or getattr(exc, 'status_code', None)
    response=getattr(exc, 'response', None)
    if code is None and response is not None:
        code=getattr(response, 'status_code', None)
    try: code=int(code)
    except (TypeError,ValueError): code=None
    message=str(exc).lower()
    if code in (429,500,502,503,504) or any(x in message for x in ('503 unavailable','429 resource_exhausted','service unavailable','temporarily unavailable')):
        return 'transient'
    return 'fatal'

def interpret_with_retries(interpreter, question, prior, *, attempts=3, sleep=time.sleep):
    """Retries transport errors only. Caller owns context and must not update it on failure."""
    if not 1 <= attempts <= 3: raise ValueError('Retry count must be 1..3')
    for i in range(attempts):
        try: return interpreter.interpret(question, prior)
        except (Rejected, ValueError): raise
        except Exception as exc:
            if classify_model_error(exc) != 'transient':
                raise ModelUnavailable('MODEL_REQUEST_FAILED: interpretation service error') from exc
            if i == attempts - 1:
                raise ModelUnavailable('MODEL_UNAVAILABLE: transient model error after bounded retries') from exc
            sleep(min(2 ** i, 2))
    raise AssertionError('Unreachable')


# Keep API schema minimal: Gemini rejects additionalProperties=False from Pydantic schema.
API_SCHEMA={
 'type':'OBJECT','properties':{
  'intent':{'type':'STRING','enum':['measure','compare','investigate','clarify']},
  'metric_id':{'type':'STRING','nullable':True},
  'start_date':{'type':'STRING','nullable':True},
  'end_date_exclusive':{'type':'STRING','nullable':True},
  'comparison_start_date':{'type':'STRING','nullable':True},
  'comparison_end_date_exclusive':{'type':'STRING','nullable':True},
  'use_prior_metric':{'type':'BOOLEAN'},
  'use_prior_period_as_comparison':{'type':'BOOLEAN'},
  'ambiguity':{'type':'STRING','nullable':True},
 }, 'required':['intent']}

class Interpreter:
    def __init__(self,model=None):
        from google import genai
        from agent.provider_policy import http_options
        key=os.getenv('GEMINI_API_KEY') or os.getenv('GOOGLE_API_KEY')
        if not key:raise Rejected('GEMINI_API_KEY is not set')
        self.client=genai.Client(api_key=key,http_options=http_options())
        self.model=model or os.getenv('OPSLENS_GEMINI_MODEL','gemini-3.5-flash-lite')
    def interpret(self,question,prior:Context|None):
        from google.genai import types
        catalog=[{'id':name,'unit':spec[3], 'source':spec[0]} for name,spec in METRICS.items()]
        instructions='''Interpret an e-commerce finance question into semantic IDs only. Never generate SQL or permissions.
Only these registered metrics are available. Do not replace requested metrics with approximations.
Dates are ISO half-open [start,end), e.g. April 2018 -> 2018-04-01..2018-05-01.
For a new standalone comparison, put earlier/"before" period in comparison_* and later/"after" in start/end.
For "compare with previous period" set use_prior_period_as_comparison=true, and put new requested period in start/end.
For "what about July" inherit prior metric with use_prior_metric=true; provide July dates.
If the question says "compare this with March" and prior exists, use prior period as after (start/end) and March as before (comparison_*), only if order is clear; otherwise clarify.
Do not invent a date, seasonality baseline, or previous period. If period missing and there is no explicit period to inherit, clarify.
No dimensions, joins, groupings or ranks are approved by this finance interface. Requests for them must clarify/decline.
For WHY/root-cause questions return intent=investigate. No measured metric alone proves a cause.
Dates must be explicit; relative dates with no explicit anchor clarify. Return JSON only.'''
        payload={'question':question,'metric_catalog':catalog,
                 'previous_successful_context':vars(prior) if prior else None}
        response=self.client.models.generate_content(model=self.model,contents=json.dumps(payload),
            config=types.GenerateContentConfig(system_instruction=instructions,
              response_mime_type='application/json',response_schema=API_SCHEMA,temperature=0))
        from investigation_traces import record_model
        record_model(response,self.model,'finance_intent')
        try:
            return Intent.model_validate(response.parsed if response.parsed is not None else json.loads(response.text))
        except (ValueError, TypeError, AttributeError) as exc:
            raise ModelResponseInvalid('MODEL_RESPONSE_INVALID: failed structured intent validation') from exc

def resolve(intent:Intent,prior:Context|None):
    if intent.intent in ('clarify','investigate'):
        raise Rejected('Investigation/clarification needs separate hypothesis workflow; no causal answer generated.' if intent.intent=='investigate' else (intent.ambiguity or 'Clarification required'))
    if intent.ambiguity:raise Rejected(intent.ambiguity)
    if intent.use_prior_metric and not prior:raise Rejected('Invalid metric inheritance: no prior context')
    # Gemini sometimes emits both the inheritance flag and its resolved ID.
    # Accept ONLY when both agree; reject any conflicting metric.
    if intent.use_prior_metric and intent.metric_id is not None and intent.metric_id != prior.metric_id:
        raise Rejected('Invalid metric inheritance: conflicting metric ID')
    metric=prior.metric_id if intent.use_prior_metric else intent.metric_id
    if metric not in METRICS:raise Rejected('Unknown or unapproved financial metric')
    if (intent.start_date is None) != (intent.end_date_exclusive is None):raise Rejected('Both period dates required')
    if not intent.start_date:raise Rejected('Explicit date period required')
    after=requested_period(intent.start_date,intent.end_date_exclusive)
    explicit_compare=(intent.comparison_start_date is not None or intent.comparison_end_date_exclusive is not None)
    if intent.use_prior_period_as_comparison and (not prior or explicit_compare):raise Rejected('Invalid comparison period inheritance')
    if intent.intent=='measure' and (intent.use_prior_period_as_comparison or explicit_compare):raise Rejected('Measure request cannot include comparison')
    before=None
    if intent.intent=='compare':
        if intent.use_prior_period_as_comparison:before=requested_period(prior.start_date,prior.end_date_exclusive)
        elif intent.comparison_start_date and intent.comparison_end_date_exclusive:
            before=requested_period(intent.comparison_start_date,intent.comparison_end_date_exclusive)
        else:raise Rejected('Comparison requires two explicit or inherited periods')
        if (before.start,before.end)==(after.start,after.end):raise Rejected('Comparison periods identical')
        if before.end > after.start:raise Rejected('Overlapping or reverse-ordered periods are not supported')
    return metric,before,after

def _confirmed_empty_period(raw: dict) -> bool:
    """Conservative fail-closed absence classification; never infer zero from NULL.

    COUNT(*) columns are non-null integer values in the authorized audit SQL.
    A mixed empty/nonempty state signals an integrity or coverage discrepancy,
    not confidently absent data.
    """
    try:
        counts = (
            raw['cohort']['placed'], raw['finance']['rows'], raw['daily']['days']
        )
        if any(isinstance(v, bool) or v is None for v in counts):
            return False
        return all(Decimal(str(v)) == 0 for v in counts)
    except (KeyError, TypeError, ValueError, ArithmeticError):
        return False


async def execute(metric,before,after,call_readonly):
    """call_readonly(sql,purpose)->one aggregate row. Called only after local intent validation."""
    async def one(period):
        raw={}
        for label,sql in audit_queries(period).items():
            raw[label]=await call_readonly(sql,'Finance period integrity: '+label)
        # Aggregate COUNT returns zero even on an empty table, whereas SUM may
        # return NULL. Distinguish a genuinely absent requested period from an
        # internally inconsistent period without converting missing data to 0.
        # All three independent counts must be explicitly zero. Missing fields,
        # malformed responses and mixed populations remain reconciliation errors.
        if _confirmed_empty_period(raw):
            raise NoSourceCoverage(
                f'NO_SOURCE_COVERAGE: no commerce orders, financial records, or '
                f'daily finance rows for [{period.start}, {period.end}). '
                'A missing period is not a zero financial metric.')
        token=audit_token(period,raw)
        plan=compile_metric(metric,period,token)
        row=await call_readonly(plan['sql'],'Governed financial metric '+metric)
        evidence=measurement_evidence(plan,{'rows':[row]},token)
        evidence['verification_checks']=[c['name'] for c in token['checks'] if c['passed']]
        return evidence
    prior=await one(before) if before else None
    current=await one(after)
    result={'intent':'compare' if before else 'measure','metric_id':metric,'measurement':current,
            'causal_claim':False,'status':'MEASURED_WITH_SCOPE_LIMITS'}
    if prior:
        if prior['unit']!=current['unit']:raise Rejected('Incompatible comparison units')
        base=Decimal(prior['value']);now=Decimal(current['value']);delta=now-base
        result['before']=prior
        result['comparison']={'absolute_change':str(delta),
            'change_unit':'percentage_points' if current['unit']=='percent' else current['unit'],
            'relative_change_pct':str(delta/abs(base)*100) if base else None,
            'relative_change_note':'Undefined for zero baseline' if not base else 'Descriptive only; differing periods may have seasonality/mix effects'}
    return result

async def mcp_query(client,sql,purpose, *, trace=None):
    from agent.phase4b1_semantic_playground import call
    response=await call(client,'run_readonly_sql',{
      'query':sql,'purpose':purpose,'expected_grain':'one aggregate row',
      'max_rows':1,'timeout_ms':20000}, **({'trace': trace} if trace is not None else {}))
    if not isinstance(response,dict) or response.get('ok') is False:
        raise Rejected('MCP query rejected: '+str(response.get('error','unknown error'))[:250] if isinstance(response,dict) else 'Invalid MCP response')
    data=response.get('data',response)
    rows=data.get('rows') if isinstance(data,dict) else None
    if not isinstance(rows,list) or len(rows)!=1 or not isinstance(rows[0],dict):
        raise Rejected('Expected exactly one aggregate row from MCP')
    return rows[0]
