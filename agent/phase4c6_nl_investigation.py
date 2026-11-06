"""Phase 4C.6: Natural-language investigation handoff to governed 4C.3-4C.5.

LLM proposes intent/periods; grounding validates every proposed period against
explicit source-question anchors. No LLM-generated SQL, no invented baseline,
no cross-domain causal claims, no changes to successful finance/graph contexts.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
from calendar import monthrange
import json
import os
import re
from typing import Any

from agent.phase4b56_dynamic_period import requested_period
from agent.phase4c3_investigation import InvestigationRequest, investigate
from agent.phase4c4_drivers import discover_drivers
from agent.phase4c5_hypotheses import evaluate_hypotheses

MONTHS = {m.lower(): i for i, m in enumerate(('January', 'February', 'March', 'April', 'May', 'June', 'July', 'August', 'September', 'October', 'November', 'December'), 1)}
MONTH_RE = re.compile(r'\b(' + '|'.join(MONTHS) + r')\s+(20\d{2}|19\d{2})\b', re.I)
ISO_RE = re.compile(r'(?<!\d)(\d{4}-\d{2}-\d{2})(?!\d)')

@dataclass(frozen=True)
class Interpretation:
    intent: str
    focus: str = 'revenue_profit_divergence'
    before_start: str | None = None
    before_end: str | None = None
    after_start: str | None = None
    after_end: str | None = None
    ambiguity: str | None = None


def explicit_periods(question: str) -> set[tuple[str,str]]:
    """Ground to explicit complete months or to adjacent explicit ISO endpoints."""
    periods: set[tuple[str,str]] = set()
    for match in MONTH_RE.finditer(question):
        year, month = int(match.group(2)), MONTHS[match.group(1).lower()]
        start = date(year, month, 1)
        end = date(year + (month == 12), (month % 12) + 1, 1)
        periods.add((start.isoformat(),end.isoformat()))
    # ISO dates can describe two explicit half-open date ranges; reject anything else.
    matches = ISO_RE.findall(question)
    if len(matches) == 4:
        periods.update(((matches[0], matches[1]),(matches[2],matches[3])))
    return periods


def _envelope(status: str, reason: str, *, route='clarification') -> dict:
    return {'route':route,'status':status,'executable':False,'reason':reason,
            'causal_claim':False}


class CompiledComparisonInterpreter:
    """Only for the explicit finance subquestion emitted by a registered coordinator."""
    @staticmethod
    def interpret(question):
        anchors = sorted(explicit_periods(question))
        if len(anchors) != 2:
            return Interpretation("diagnostic_investigation")
        before, after = anchors
        return Interpretation("diagnostic_investigation", before_start=before[0], before_end=before[1],
                              after_start=after[0], after_end=after[1])


def ground_interpretation(question: str, proposal: Interpretation) -> tuple[InvestigationRequest|None,dict|None]:
    if not isinstance(question,str) or not question.strip() or len(question)>4000:
        return None,_envelope('NEEDS_CLARIFICATION','Please provide a concise business question and two explicit comparison periods.')
    if not isinstance(proposal,Interpretation) or proposal.intent != 'diagnostic_investigation':
        return None,_envelope('UNSUPPORTED_INVESTIGATION','The request was not grounded as a supported diagnostic investigation.',route='unsupported')
    if proposal.focus != 'revenue_profit_divergence':
        return None,_envelope('UNSUPPORTED_INVESTIGATION','Only revenue versus contribution-profit divergence is supported by the current governed investigation.',route='unsupported')
    dates=(proposal.before_start,proposal.before_end,proposal.after_start,proposal.after_end)
    if not all(isinstance(x,str) for x in dates):
        return None,_envelope('NEEDS_CLARIFICATION','Which two periods should I compare? Please specify both, such as February 2018 and March 2018.')
    try:
        before=requested_period(dates[0],dates[1]); after=requested_period(dates[2],dates[3])
        if before.end > after.start:
            return None,_envelope('NEEDS_CLARIFICATION','Comparison periods must be chronological and non-overlapping.')
    except (ValueError,TypeError,AttributeError) as exc:
        return None,_envelope('NEEDS_CLARIFICATION','The comparison periods are invalid or unsupported: '+str(exc)[:120])
    anchors=explicit_periods(question)
    if (before.start,before.end) not in anchors or (after.start,after.end) not in anchors:
        return None,_envelope('NEEDS_CLARIFICATION','Both comparison periods must be explicitly stated; I will not infer a baseline or silently expand a timeframe.')
    if len(anchors)!=2:
        return None,_envelope('NEEDS_CLARIFICATION','Please specify exactly two comparison periods for this investigation.')
    return InvestigationRequest(before.start,before.end,after.start,after.end),None


SCHEMA = {'type':'OBJECT','properties':{
    'intent':{'type':'STRING','enum':['diagnostic_investigation','other']},
    'focus':{'type':'STRING'},
    'before_start':{'type':'STRING','nullable':True},
    'before_end':{'type':'STRING','nullable':True},
    'after_start':{'type':'STRING','nullable':True},
    'after_end':{'type':'STRING','nullable':True},
    'ambiguity':{'type':'STRING','nullable':True},
},'required':['intent','focus']}

class GeminiInvestigationInterpreter:
    def __init__(self, model: str|None = None):
        from google import genai
        from agent.provider_policy import http_options
        key = os.getenv('GEMINI_API_KEY') or os.getenv('GOOGLE_API_KEY')
        if not key:
            raise ValueError('GEMINI_API_KEY not configured')
        self.client=genai.Client(api_key=key,http_options=http_options())
        self.model=model or os.getenv('OPSLENS_GEMINI_MODEL','gemini-3.5-flash-lite')

    def interpret(self, question: str) -> Interpretation:
        from google.genai import types
        system=(
            'You are an intent and period extractor, NOT an analyst. Output JSON only. '
            'Use diagnostic_investigation only for explaining revenue increase versus '
            'contribution profit decrease or their apparent divergence. '
            'The only supported focus is revenue_profit_divergence. '
            'Extract TWO explicit chronological periods exactly from the question. '
            'For a complete named month, emit [first day of month, first day of next month); '
            'for explicit ISO ranges use their exact endpoints. '
            'If one period, baseline, metric meaning, or time range is missing, emit null fields. '
            'Never assume preceding month, year, defaults, or source coverage. '
            'Do not generate SQL or compute any value. No claims of cause.'
        )
        response=self.client.models.generate_content(
            model=self.model,contents=question,
            config=types.GenerateContentConfig(system_instruction=system,
                response_mime_type='application/json',response_schema=SCHEMA,temperature=0,
                automatic_function_calling=types.AutomaticFunctionCallingConfig(disable=True)))
        data=response.parsed if response.parsed is not None else json.loads(response.text)
        if hasattr(data,'model_dump'):data=data.model_dump()
        if not isinstance(data,dict) or set(data)-set(SCHEMA['properties']):
            raise ValueError('Malformed Gemini interpretation')
        return Interpretation(**data)


async def run_investigation(question: str, interpreter, finance_reader, *, max_hypotheses:int=5) -> dict:
    """Enforces full grounding before first DB call. Existing executors own SQL."""
    proposal=interpreter.interpret(question)
    request,blocked=ground_interpretation(question,proposal)
    if blocked is not None:return blocked
    assert request is not None
    core=await investigate(request,finance_reader)
    async def component_reader(sql,purpose):
        row=await finance_reader(sql,purpose)
        if not isinstance(row,dict):raise ValueError('Invalid MCP aggregate response')
        return {'rows':[row]}
    enriched=await discover_drivers(core,component_reader)
    evaluated=evaluate_hypotheses(enriched,max_hypotheses=max_hypotheses)
    return {'route':'investigation','status':evaluated['status'],
            'executable':True,'causal_claim':False,
            'periods':enriched['periods'],'premise':enriched['premise'],
            'investigation_status':enriched['status'],
            'driver_discovery_status':enriched['driver_discovery']['status'],
            'hypothesis_evaluation':evaluated,
            'limitations':enriched.get('limitations',[]),
            'note':'Measured accounting contributions are not proof of operational or causal mechanisms.'}
