import re

def contextual(q,known,pending):
 from agent.session_context import MONTH,period,clarification
 explicit=bool(re.search(r'\b(refunds?|returns|returned orders|return (?:rate|events?|counts?|concentration|amounts?))\b',q,re.I))
 active=known.get('route')=='refund_concentration' or pending.get('capability')=='refund_concentration'
 follow=bool(re.fullmatch(r'(?:what about |how about |compare (?:that|it) with |no,? (?:i meant )?)?'+MONTH,q,re.I))
 detail=bool(re.search(r'concentrat|sellers?|break.?down|where|why|which',q,re.I))
 if not explicit and not (active and (follow or re.fullmatch(r'(?:which |what about )?sellers',q,re.I) or re.fullmatch(r'20\d{2}',q))):return None
 if re.search(r'\b(sku|product|category|categories|caused|responsible|late|delivery|region|state|city|reason|cash.flow|over|under|above|below|only|excluding)\b|on.time|for seller\b|refund.date|return.date',q,re.I):
  blocked=clarification('This capability supports all purchased orders in one month and exclusive seller cohorts. Filtered cohorts, reason/SKU attribution, refund-date reporting and causal responsibility are not registered.')
  blocked['status']='NOT_YET_SUPPORTED';return None,blocked,[]
 dates=list(re.finditer(MONTH,q,re.I));inherited=[]
 if pending.get('capability')=='refund_concentration' and re.fullmatch(r'20\d{2}',q):
  dates=list(re.finditer(MONTH,pending.get('question',''),re.I))
  if len(dates)==1:
   start,end=period(dates[0].group(1),q)
   return {'kind':'refund_concentration','start':start,'end':end,'detail':pending.get('detail',True)},None,[{'field':'year','source':'clarification','value':q}]
 if len(dates)==1:
  month,year=dates[0].groups()
  if year is None and active and len(known.get('years',[]))==1:year=known['years'][0];inherited=[{'field':'year','source':'last_validated_result','value':year}]
  if year is None:return None,clarification('Which purchase year should the return/refund investigation use?'),[]
  start,end=period(month,year)
 elif not dates and known.get('period') and (active or explicit):
  start,end=known['period'];inherited=[{'field':'period','source':'last_validated_result','value':[start,end]}]
 else:return None,clarification('Which single purchase month and year should the return/refund investigation use?'),[]
 return {'kind':'refund_concentration','start':start,'end':end,'detail':detail or (follow and known.get('refund_intent',False))},None,inherited
