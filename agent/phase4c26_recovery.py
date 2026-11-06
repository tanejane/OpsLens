"""Bounded clarification recovery over 4C.25; no authorization changes.

Accept explicit period revisions, minimal Chinese month names, and explicit topic
changes while a sales clarification is pending. Never infer a category or metric.
"""
import re
from agent.phase4c25_clarification import ClarificationSession, Pending, clarification, MONTH_RE, METRICS, CAT, TOPIC, CANCEL

CN_MONTH = {'一':1,'二':2,'三':3,'四':4,'五':5,'六':6,'七':7,'八':8,'九':9,'十':10,'十一':11,'十二':12}
MONTH_NAMES = 'January February March April May June July August September October November December'.split()
CORRECTION = re.compile(r'^\s*(?:(?:no[,.!?]?\s*)?(?:i\s+meant|make\s+that|rather|instead|change\s+(?:it\s+)?to)\s+|no[,.]?\s*)',re.I)


def period_choice(q):
    """Return month-year only for an explicit, fully consumed choice."""
    q=q.strip().rstrip('?.! ').strip()
    m=MONTH_RE.fullmatch(q)
    if m:return m.group(1).capitalize()+' '+m.group(2)
    m=re.fullmatch(r'(?:(20\d{2})年?)?\s*(十一|十二|十|[一二三四五六七八九])月\s*(20\d{2})?',q)
    if m:
        year=m.group(1) or m.group(3)
        if year and (not m.group(1) or not m.group(3) or m.group(1)==m.group(3)):
            return MONTH_NAMES[CN_MONTH[m.group(2)]-1]+' '+year
    return None

class RecoverySession(ClarificationSession):
    def __init__(self, language_session):
        super().__init__(language_session)
        self.investigation_pending = None

    def remember_finance(self, metric, start, end, route):
        """Commit a successfully validated contextual execution to existing state."""
        from dataclasses import replace
        from agent.phase4b57_nl_dynamic_finance import Context
        product = self.language_session.product_session
        prior = product.prior
        state = prior.unified_state
        prior.unified_state = replace(state, conversation=replace(state.conversation,
            finance=Context(metric,start,end),last_successful_route=route),last_successful_domain='finance')
        prior.active_domain = route
        product.active_domain = None

    async def dispatch(self,question,*args):
        if not isinstance(question,str) or not question.strip():
            return clarification('Please enter a question')
        q=question.strip()
        if not self.pending:
            return await super().dispatch(q,*args)
        # Delegate original cancellation and suspicious syntax checks.
        if CANCEL.fullmatch(q) or re.search(r';|--|/\*|\*/',q):
            return await super().dispatch(q,*args)
        # Explicit correction only; no fuzzy parsing or implicit cross-domain overrides.
        is_correction=bool(CORRECTION.match(q))
        core=CORRECTION.sub('',q,count=1).strip() if is_correction else q
        corrected_period=period_choice(core)
        pending=self.pending
        if corrected_period:
            self.pending=Pending(corrected_period,pending.metric)
            if pending.metric=='financial_revenue':
                self.pending=None
                return await self.language_session.dispatch('What was revenue in '+corrected_period+'?',*args)
            if pending.metric in ('item_gmv','units_sold'):
                return clarification('Which approved category? Currently health and beauty / beleza_saude.',self.pending)
            return clarification('Which measure: financial revenue, item GMV, or units sold?',self.pending)
        if is_correction:
            canonical=core.rstrip('?.! ').strip()
            metric=next((k for k,p in METRICS.items() if p.fullmatch(canonical)),None)
            if metric:
                self.pending=Pending(pending.period,None)
                return await super().dispatch(canonical,*args)
            if CAT.fullmatch(canonical) and pending.metric in ('item_gmv','units_sold'):
                return await super().dispatch(canonical,*args)
            return clarification('I could not verify that correction. Please specify a month and year, an approved metric, or an approved category.',pending)
        return await super().dispatch(q,*args)
