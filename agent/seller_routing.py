import re

def contextual(q,known,pending):
    from agent.session_context import MONTH,period,clarification
    explicit=bool(re.search(r'\bsellers?\b',q,re.I) and re.search(r'\b(delivery|deliveries|late|delays?)\b',q,re.I))
    active=known.get('route')=='seller_concentration' or pending.get('capability')=='seller_concentration'
    if pending.get('capability')=='seller_concentration' and re.fullmatch(r'20\d{2}',q):
        months=list(re.finditer(MONTH,pending.get('question',''),re.I))
        if len(months)==1:
            start,end=period(months[0].group(1),q)
            return {'kind':'seller_concentration','start':start,'end':end},None,[{'field':'month','value':months[0].group(1),'source':'clarification'}]
    follow=bool(re.fullmatch(r'(?:what about |how about |compare (?:that|it) with )?'+MONTH,q,re.I))
    contextual_seller=bool(re.search(r'\bsellers?\b',q,re.I)) and known.get('route') in ('delivery_review_comparison','delivery_measure','seller_concentration')
    if (explicit or contextual_seller) and re.search(r'\b(review|reviews|rating|ratings|profit|revenue)\b',q,re.I):
        blocked=clarification('Seller-level comparison currently supports delivery lateness only. Please ask for delivery concentration; seller review or financial comparisons are not registered.')
        blocked['status']='NOT_YET_SUPPORTED'
        return None,blocked,[]
    if not explicit and not (active and follow) and not contextual_seller:return None
    dates=list(re.finditer(MONTH,q,re.I)); inherited=[]
    if not dates and contextual_seller and known.get('period'):
        dates=None;start,end=known['period'];inherited=[{'field':'period','value':[start,end],'source':'last_validated_result'}]
    elif len(dates)==1:
        month,year=dates[0].groups()
        if year is None and active and len(known.get('years',[]))==1:year=known['years'][0];inherited=[{'field':'year','value':year,'source':'last_validated_result'}]
        if year is None:return None,clarification('Which purchase year should the seller delivery comparison use?'),[]
        start,end=period(month,year)
    else:return None,clarification('Which purchase month and year should the seller delivery comparison use?'),[]
    return {'kind':'seller_concentration','start':start,'end':end},None,inherited
