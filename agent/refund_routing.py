import re

def contextual(q,known,pending):
 from agent.session_context import MONTH,period,clarification
 explicit=bool(re.search(r'\b(refunds?|returns|returned orders|return (?:rate|events?|counts?|concentration|amounts?))\b',q,re.I))
 active=known.get('route')=='refund_concentration' or pending.get('capability')=='refund_concentration'
 follow=bool(re.fullmatch(r'(?:what about |how about |compare (?:that|it) with |no,? (?:i meant )?)?'+MONTH,q,re.I))
 detail=bool(re.search(r'concentrat|sellers?|break.?down|where|why|which',q,re.I))
 if not explicit and not (active and (follow or re.fullmatch(r'(?:which |what about )?sellers',q,re.I) or re.fullmatch(r'20\d{2}',q))):return None
 advanced = re.search(
     r"\b(?:promot\w*|campaigns?|expos(?:ed|ure)|"
     r"strat(?:a|if\w*)|order[- ]value|confound\w*|"
     r"caus(?:e|es|ed|al|ation)|"
     r"fulfil\w*|fulfill\w*|"
     r"invoices?|accruals?|supplier)\b",
     q,
     re.I,
 )

 if advanced:
     blocked = clarification(
         "An overall monthly refund measurement cannot establish "
         "promotion effects, order-value stratification, fulfillment "
         "performance, or supplier/accrual reconciliation. "
         "The requested analysis is not fully registered."
     )
     blocked["status"] = "NOT_YET_SUPPORTED"
     blocked["executable"] = False
     blocked["causal_claim"] = False
     blocked["approved_for_mcp"] = False
     blocked["evidence_requirements"] = [
         "Validated data and a governed analytical capability for "
         "the requested exposure, strata, or additional domain",
         "Explicit population, period, join-grain and "
         "reconciliation checks",
     ]
     blocked["next_step"] = (
         "Register and validate the required analysis separately; "
         "do not infer it from an aggregate refund rate."
     )
     return None, blocked, []
 # Stage 5.15H.9: block known unsupported refund scopes.
 unsupported_scope = re.search(
     r"\b(?:"
     r"credit[\s-]*cards?|"
     r"payment[\s-]*methods?|"
     r"first[\s-]*time[\s-]+(?:buyers?|customers?|purchasers?)|"
     r"loyalty[\s-]*tiers?|"
     r"discount[\s-]*codes?|"
     r"mobile[\s-]*apps?"
     r")\b",
     q,
     re.I,
 )

 if unsupported_scope:
     blocked = clarification(
         "The monthly refund capability cannot apply the requested "
         "payment-method, first-time-buyer, loyalty-tier, "
         "discount-code, or purchase-channel restriction. "
         "A separately validated analytical capability is required."
     )
     blocked["status"] = "NOT_YET_SUPPORTED"
     blocked["executable"] = False
     blocked["approved_for_mcp"] = False
     blocked["causal_claim"] = False
     blocked["evidence_requirements"] = [
         "Governed cohort or grouping definition for the restriction",
         "Validated source fields, join grain, denominator, and period",
     ]
     blocked["next_step"] = (
         "Validate and register the restricted analysis separately; "
         "do not substitute the overall monthly refund result."
     )
     return None, blocked, []
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
