"""Stateful, opt-in clarification in front of Phase 4C.24 LanguageSession.

Only explicit metric and category choices are accepted. Never creates SQL or
widens tool authorization. A pending clarification is cleared by a new topic.
"""
from dataclasses import dataclass
import re

MONTHS = 'january february march april may june july august september october november december'.split()
MONTH_RE = re.compile(r'\b(' + '|'.join(MONTHS) + r')\s+(20\d{2})\b', re.I)
SALES = re.compile(r'\b(?:sales|selling|sold)\b', re.I)
VAGUE = re.compile(r'^\s*(?:(?:how\s+(?:were|was|are|is)|show\s+me|what\s+(?:about|were|was))\s+)?(?:the\s+|our\s+)?sales(?:\s+(?:doing|performance))?(?:\s+(?:in|for|during)\s+(.+?))?\s*[?.!]?\s*$',re.I)
METRICS = {
 'financial_revenue':re.compile(r'^(?:financial\s+revenue|audited\s+(?:financial\s+)?revenue|revenue)$',re.I),
 'item_gmv':re.compile(r'^(?:item\s+gmv|gmv)$',re.I),
 'units_sold':re.compile(r'^(?:units\s+sold|units|item\s+units)$',re.I),
}
CAT = re.compile(r'^(?:health\s+(?:and|&)\s+beauty|health_beauty|beleza_saude)$',re.I)
TOPIC = re.compile(r'\b(?:delivery|late|rating|review|profit|investigate|refund|seller|customer|why|stockout)\b',re.I)
CANCEL = re.compile(r'^(?:cancel|never\s+mind|nevermind|stop)$',re.I)

@dataclass(frozen=True)
class Pending:
    period: str | None = None
    metric: str | None = None

def clarification(reason, pending=None):
    d={'route':'language_clarification','status':'NEEDS_CLARIFICATION','executable':False,
       'reason':reason,'causal_claim':False,'inventory_claim_allowed':False}
    if pending:
        d['retained']={'period':pending.period,'metric':pending.metric}
    return d

class ClarificationSession:
    def __init__(self,language_session):
        self.language_session=language_session
        self.pending=None

    async def dispatch(self,question,*args):
        if not isinstance(question,str) or not question.strip():
            return clarification('Please enter a question')
        q=question.strip()
        if CANCEL.fullmatch(q):
            self.pending=None
            return {'route':'language_clarification','status':'CANCELLED','executable':False,'causal_claim':False,'inventory_claim_allowed':False}
        # Refuse unsafe notation before examining pending choices.
        if re.search(r';|--|/\*|\*/',q):
            self.pending=None
            return clarification('Unsupported query syntax; please rephrase')
        if self.pending:
            pending=self.pending
            if TOPIC.search(q) or (MONTH_RE.search(q) and not MONTH_RE.fullmatch(q.rstrip('?.! ').strip())) or (len(q.split())>5 and not VAGUE.fullmatch(q)):
                self.pending=None
                return await self.language_session.dispatch(q,*args)
            metric=next((k for k,p in METRICS.items() if p.fullmatch(q.rstrip('?.! ').strip())),None)
            if metric and pending.metric is None:
                self.pending=Pending(pending.period,metric)
                if metric=='financial_revenue':
                    if not pending.period:return clarification('Which month and year?',self.pending)
                    self.pending=None
                    return await self.language_session.dispatch('What was revenue in '+pending.period+'?',*args)
                return clarification('Which approved category? Currently health and beauty / beleza_saude.',self.pending)
            if pending.metric in ('item_gmv','units_sold') and CAT.fullmatch(q.rstrip('?.! ').strip()):
                if not pending.period:
                    return clarification('Which month and year? Example: June 2018.',pending)
                self.pending=None
                metric_phrase='item GMV' if pending.metric=='item_gmv' else 'units sold'
                normalized_category='health and beauty'
                composed=(('How many '+normalized_category+' products were sold in '+pending.period+'?') if pending.metric=='units_sold' else ('What was the item GMV for '+normalized_category+' in '+pending.period+'?'))
                return await self.language_session.dispatch(composed,*args)
            if MONTH_RE.fullmatch(q.rstrip('?.! ').strip()) and not pending.period:
                self.pending=Pending(q.rstrip('?.! ').strip(),pending.metric)
                if pending.metric=='financial_revenue':
                    self.pending=None
                    return await self.language_session.dispatch('What was revenue in '+q.rstrip('?.! ').strip()+'?',*args)
                if pending.metric in ('item_gmv','units_sold'):
                    return clarification('Which approved category? Currently health and beauty / beleza_saude.',self.pending)
                return clarification('Which measure: financial revenue, item GMV, or units sold?',self.pending)
            return clarification('Please select the requested metric or approved category, or ask a new question.',pending)
        vague=VAGUE.fullmatch(q)
        if vague:
            period_match=MONTH_RE.search(vague.group(1) or '')
            period=(period_match.group(1).capitalize()+' '+period_match.group(2)) if period_match else None
            self.pending=Pending(period,None)
            return clarification('Which measure: financial revenue, item GMV, or units sold?',self.pending)
        return await self.language_session.dispatch(q,*args)
