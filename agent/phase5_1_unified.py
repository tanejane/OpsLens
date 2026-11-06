"""Phase 5.1 bounded, opt-in Gemini interpretation bridge.

This module never grants MCP access. It wraps the previously tested RecoverySession,
which must still approve every synthesized request and invoke its governed reader.
LLM proposals are strictly advisory, independently cross-checked against the original
user message, and never transformed into SQL.
"""
import re
from agent.phase4c27a_interpreter import interpret as llm_interpret, InterpretationRejected
from agent.phase4c25_clarification import MONTHS

MONTH_PATTERN = re.compile(r'\b('+'|'.join(MONTHS)+r')\s+(20\d{2})\b', re.I)
MONTH_SHORT = re.compile(r'\b(jan|feb|mar|apr|may|jun|jul|aug|sep|sept|oct|nov|dec)\s*[\'’]?\s*(20\d{2}|\d{2})\b',re.I)
MNUM={'jan':1,'feb':2,'mar':3,'apr':4,'may':5,'jun':6,'jul':7,'aug':8,'sep':9,'sept':9,'oct':10,'nov':11,'dec':12}
SUSPICIOUS=re.compile(r'(?:--|/\*|\*/|\b(?:drop|delete|insert|update|alter|grant|revoke)\b|ignore\s+(?:all\s+)?(?:previous|prior)\s+instructions)',re.I)
PRODUCT_CATEGORY=re.compile(r'\b(?:health\s+(?:and|&)\s+beauty|health_beauty|beleza_saude|beuty|beauty)\b',re.I)
METRIC_WORDS={
 'effective_revenue':re.compile(r'\b(?:revenue|reveneu|revnue)\b',re.I),
 'item_gmv':re.compile(r'\b(?:item\s+gmv|gmv)\b',re.I),
 'units_sold':re.compile(r'\b(?:units?|sold|products?\s+were\s+sold|how\s+many)\b',re.I),
 'late_delivery_rate':re.compile(r'\b(?:late\s+(?:delivery|delivry)|delivery\s+late|lateness)\b',re.I),
 'average_delivery_days':re.compile(r'\b(?:average\s+(?:delivery|delivry)|delivery\s+days)\b',re.I),
 'average_review_score':re.compile(r'\b(?:review\s+score|average\s+rating)\b',re.I),
 'low_rating_rate':re.compile(r'\b(?:low\s+rating|bad\s+review)\b',re.I),
 'review_coverage':re.compile(r'\b(?:review\s+coverage)\b',re.I),
 'category_order_count':re.compile(r'\b(?:orders?|how\s+many\s+orders)\b',re.I),
 'average_item_price':re.compile(r'\b(?:average\s+(?:item\s+)?price)\b',re.I),
 'category_gmv_share':re.compile(r'\b(?:share|percentage|percent)\b',re.I),
}

def result(status,reason,**extra):
    return {'route':'unified_interpreter','status':status,'executable':False,'reason':reason,
            'approved_for_mcp':False,'causal_claim':False,'inventory_claim_allowed':False,**extra}

def original_period(text):
    periods=set()
    for m in MONTH_PATTERN.finditer(text):periods.add((MONTHS.index(m.group(1).lower())+1,int(m.group(2))))
    for m in MONTH_SHORT.finditer(text):
        yr=int(m.group(2));yr=2000+yr if yr<100 else yr
        periods.add((MNUM[m.group(1).lower()],yr))
    return periods

def preflight(question):
    """Restore the bounded 5.1B handoff; never authorize an analysis or SQL."""
    if (not isinstance(question,str) or not question.strip() or len(question)>500
        or SUSPICIOUS.search(question) or ';' in question):
        return None
    month='(?:'+'|'.join(MONTHS)+')'
    shared=re.search(r'\b(?:from\s+'+month+r'\s+to|between\s+'+month+r'\s+and)\s+'+month+r'\s+20\d{2}\b',question,re.I)
    if (shared and re.search(r'\b(?:why|explain|investigat\w*)\b',question,re.I)
        and re.search(r'\brevenue\b',question,re.I) and re.search(r'\bprofit\b',question,re.I)):
        return ('delegate',None)  # Original question still passes downstream grounding.
    broad=re.fullmatch(r'\s*(?:eh\s+)?(?:how\s+(?:was|were|is|are)\s+)?sales(?:\s+in\s+('+month+r')(?:\s+(20\d{2}))?)?\s*(?:ah)?\s*[?.!]?\s*',question,re.I)
    if broad:
        if broad.group(1) and not broad.group(2):
            return ('clarify','Which sales measure and year? Specify financial revenue, item GMV, or units sold, with month and year.')
        return ('delegate',None)
    return None


def bridge(question, proposal):
    """Pure validation: returns routeable English only with independently corroborated slots."""
    if not isinstance(question,str) or not question.strip() or len(question)>500 or SUSPICIOUS.search(question):
        return result('NOT_INTERPRETED','Unsafe or invalid source question')
    if proposal.get('status')!='INTERPRETATION_PROPOSED' or proposal.get('original_question')!=question:
        return result('NOT_INTERPRETED','Unvalidated or mismatched model proposal')
    p=proposal['interpretation'];intent=p['intent'];m=p['metrics'];period=p['period']
    if intent=='unsupported':return result('NOT_YET_SUPPORTED','Requested capability is unsupported')
    if intent=='financial_investigation':
        if p['requires_clarification'] or not {'effective_revenue','contribution_profit'}.issubset(set(m)):
            return result('NEEDS_CLARIFICATION','Financial investigation needs validated revenue and contribution-profit intent and a complete comparison period')
        if period['month'] is None or period['year'] is None or (period['month'],period['year']) not in original_period(question):
            return result('NEEDS_CLARIFICATION','Confirm the investigation month and year')
        if not re.search(r'\b(?:why|investigat|explain)\w*\b',question,re.I) or not re.search(r'\b(?:revenue|reveneu|revnue)\b',question,re.I) or not re.search(r'\b(?:profit|profitt)\b',question,re.I):
            return result('NEEDS_CLARIFICATION','Investigation premise is not confirmed in original question')
        return result('HANDOFF_REQUIRED','Use the original question with existing guarded investigation router')
    if intent=='clarification' or p['requires_clarification']:
        # Cannot invent a time period, category or metric even for clarification.
        return result('NEEDS_CLARIFICATION','Please specify the exact metric, month and year'+(' and approved category' if intent=='product_measure' else ''),
                      suggested_missing=p['missing_information'])
    if len(m)!=1:return result('NEEDS_CLARIFICATION','Exactly one approved metric must be specified')
    metric=m[0];mo=period['month'];year=period['year']
    if mo is None or year is None:return result('NEEDS_CLARIFICATION','Please provide both month and year')
    if (mo,year) not in original_period(question):return result('NEEDS_CLARIFICATION','Model period was not independently confirmed in the original question')
    if not METRIC_WORDS.get(metric) or not METRIC_WORDS[metric].search(question):
        return result('NEEDS_CLARIFICATION','Model metric was not independently confirmed in the original question')
    if intent=='product_measure':
        if p['category']!='beleza_saude' or not PRODUCT_CATEGORY.search(question):
            return result('NEEDS_CLARIFICATION','Approved product category not confirmed in original question')
        supported={ 'item_gmv':'What was the item GMV for health and beauty in {period}?',
                    'units_sold':'How many health and beauty products were sold in {period}?',
                    'category_order_count':'How many health and beauty orders in {period}?',
                    'average_item_price':'What was the average item price for health and beauty in {period}?',
                    'category_gmv_share':'What percentage of item GMV was health and beauty in {period}?' }
    elif intent=='finance_measure':
        supported={'effective_revenue':'What was revenue in {period}?'}
    elif intent=='delivery_measure':
        supported={'late_delivery_rate':'What is the late delivery rate in {period}?',
                   'average_delivery_days':'What were the average delivery days in {period}?'}
    elif intent=='review_measure':
        supported={'average_review_score':'What was the average review score in {period}?',
                   'low_rating_rate':'What was the low rating rate in {period}?',
                   'review_coverage':'What was review coverage in {period}?'}
    else:return result('NEEDS_CLARIFICATION','No supported domain route')
    if metric not in supported:return result('NEEDS_CLARIFICATION','Metric and domain combination not registered')
    canonical=f'{MONTHS[mo-1].capitalize()} {year}'
    return {'status':'ROUTE_CANDIDATE','route':'unified_interpreter','executable':False,'approved_for_mcp':False,
            'canonical_question':supported[metric].format(period=canonical),'metric_id':metric,
            'period':[f'{year:04d}-{mo:02d}-01'], 'interpretation_only':True}

class UnifiedSession:
    """One session entrypoint; Gemini is optional, not an authorization provider."""
    def __init__(self,recovery_session,model_client=None,gemini_enabled=True):
        self.recovery=recovery_session
        self.model_client=model_client
        self.gemini_enabled=gemini_enabled

    async def dispatch(self,question,*args,deterministic_fallback=None):
        # Preserve existing multi-turn state and deterministic fallback.
        if self.recovery.pending or not self.gemini_enabled:
            return await self.recovery.dispatch(question,*args)
        if not isinstance(question,str) or not question.strip():return result('NEEDS_CLARIFICATION','Please enter a question')
        if len(question)>500 or SUSPICIOUS.search(question):return result('NOT_INTERPRETED','Unsafe or invalid source question')
        preliminary=preflight(question)
        if preliminary is not None:
            action,reason=preliminary
            if action=='delegate':return await self.recovery.dispatch(question,*args)
            return result('NEEDS_CLARIFICATION',reason)
        if self.model_client is None:
            return await self.recovery.dispatch(question,*args)
        try:
            proposal=await llm_interpret(question,self.model_client)
            gate=bridge(question,proposal)
        except (InterpretationRejected,ValueError,TypeError) as e:
            return await self._fallback(question,args,e,'INVALID_OUTPUT',deterministic_fallback)
        except Exception as e:
            return await self._fallback(question,args,e,'UNAVAILABLE',deterministic_fallback)
        if gate['status']=='NEEDS_CLARIFICATION' and proposal['interpretation']['intent']=='clarification':
            return await self.recovery.dispatch(question,*args)
        if gate['status']=='ROUTE_CANDIDATE':
            # A governed downstream router must still independently validate the canonical request.
            response=await self.recovery.dispatch(gate['canonical_question'],*args)
            response=dict(response)
            response['unified_interpretation']={'original_question':question,'canonical_question':gate['canonical_question'],
               'policy':'independent_metric_period_category_confirmation_v1','gemini_executed_tools':False}
            return response
        # Handoff for explicit investigations uses the ORIGINAL question only.
        if gate['status']=='HANDOFF_REQUIRED':
            return await self.recovery.dispatch(question,*args)
        return gate

    async def _fallback(self, question, args, error, status, fallback=None):
        # Only the original user input is retried through existing validators.
        try:
            if fallback is not None:
                response = await fallback()
            else:
                # The fallback itself must not re-enter the failing provider via
                # a downstream router or interpreter.
                class NoModel:
                    def propose(self,*args): raise RuntimeError('Model disabled during fallback')
                    interpret=propose
                bounded=list(args)
                for index in (1,2,4,7):
                    if index<len(bounded):bounded[index]=NoModel()
                response = await self.recovery.dispatch(question,*bounded)
        except Exception:
            response = result('INTERPRETER_UNAVAILABLE','Model unavailable and no deterministic route completed; no measurements inferred')
        return {**response,'provider_fallback':{'status':status,'error_type':type(error).__name__}}
