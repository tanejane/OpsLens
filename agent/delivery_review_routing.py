"""Bounded routing slots; all execution uses the fixed comparison compiler."""
import re
from copy import deepcopy
PERIOD_SCHEMA={'type':'OBJECT','properties':{'start':{'type':'STRING'},'end':{'type':'STRING'}},'required':['start','end']}

def period_proposal(raw):
    """Accept the provider's singleton JSON envelope, never multiple periods."""
    import json
    value=json.loads(raw)
    if isinstance(value,list) and len(value)==1:
        value=value[0]
    return value

def relevant(q):
    from agent.phase5_2e_multidomain_router import decision
    if decision(q) is not None:
        return False
    return bool(re.search(r'\b(late|delayed|on.time)\b',q,re.I) and re.search(r'\b(review|reviews|rating|ratings|satisfaction|scores?)\b',q,re.I))

def contextual(q,known,pending,last):
    from agent.session_context import MONTH, period, clarification
    active=known.get('route')=='delivery_review_comparison' or pending.get('capability')=='delivery_review_comparison'
    if pending.get('capability')=='delivery_review_comparison' and re.fullmatch(r'20\d{2}',q):
        previous=list(re.finditer(MONTH,pending.get('question',''),re.I))
        if len(previous)==1:
            start,end=period(previous[0].group(1),q)
            return {'kind':'delivery_review_comparison','start':start,'end':end},None,[{'field':'month','value':previous[0].group(1),'source':'clarification'}]
    follow=bool(re.fullmatch(r'(?:what about |how about |compare (?:that|it) with |no,? (?:i meant )?)?'+MONTH,q,re.I))
    if active and re.fullmatch(r'(?:why(?: is that)?|what caused (?:that|it)|go deeper|break down(?: further)?)',q,re.I):
        if last:
            result=deepcopy(last['payload'])
            result['limitations']=[*result.get('limitations',[]),'No approved causal or finer-segment investigation is registered for this comparison. Existing findings remain available.']
            return None,result,[]
    if not relevant(q) and not (active and follow): return None
    dates=list(re.finditer(MONTH,q,re.I))
    if len(dates)!=1: return None,clarification('Which purchase month and year should the late versus on-time review comparison use?'),[]
    month,year=dates[0].groups(); inherited=[]
    if year is None and active and len(known.get('years',[]))==1:
        year=known['years'][0]; inherited=[{'field':'year','value':year,'source':'last_validated_result'}]
    if year is None: return None,clarification('Which year should this purchase-month comparison use?'),[]
    start,end=period(month,year)
    return {'kind':'delivery_review_comparison','start':start,'end':end},None,inherited

async def route(question,reader,model=None):
    from agent.session_context import safe
    if not safe(question) or not relevant(question): return None
    # Model may interpret phrasing, but cannot select SQL, sources or metrics.
    action,immediate,_=contextual(question,{}, {},None)
    if model is not None and action:
        import json
        from agent.phase4c27a_interpreter import gemini_client
        options={'response_schema':PERIOD_SCHEMA} if model is gemini_client else {}
        proposed=period_proposal(await model('Extract the explicitly stated purchase month and year. start is the first day of that month; end is the first day of the following month, exclusive. Return one JSON object with only start and end as ISO YYYY-MM-DD dates. No SQL or causality.',question,**options))
        if proposed != {'start':action['start'],'end':action['end']}:
            from agent.session_context import clarification
            return clarification('Please confirm the purchase month and year for the cohort comparison.')
    if immediate: return immediate
    from agent.delivery_review_comparison import investigate
    return await investigate(action['start'],action['end'],reader)
