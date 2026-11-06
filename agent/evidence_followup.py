"""Evidence-conditioned extensions of registered operations; never model SQL."""
from copy import deepcopy
from agent.investigation_state import BudgetStop
from agent.phase4c15_delivery import measure as delivery_measure
from agent.phase4c11_satisfaction import measure as review_measure

REGISTRY={'delivery_missingness':('delivery_evidence_coverage',delivery_measure),
          'review_population_coverage':('review_coverage',review_measure)}

def candidates(result,done):
    evidence=result.get('evidence',{})
    if result.get('route')=='refund_concentration':
        return [('refund_concentration','The question requests concentration and recorded returns warrant exclusive seller attribution.')] if result.get('refund_intent') is True and evidence.get('population',{}).get('returned_orders',0)>0 and 'refund_concentration' not in done else []
    if result.get('route')=='seller_concentration':
        return [('seller_concentration','The user asked about sellers and validated late orders warrant an exclusive seller partition.')] if result.get('seller_intent') is True and evidence.get('population',{}).get('late_orders',0)>0 and 'seller_concentration' not in done else []
    if result.get('route')!='delivery_review_comparison': return []
    groups=evidence.get('cohorts',{})
    choices=[]
    if groups.get('unclassified',{}).get('orders',0)>0:
        choices.append(('delivery_missingness','Unclassified deliveries could change how broadly the rating comparison applies.'))
    if evidence.get('missing_review_rows',0)>0:
        choices.append(('review_population_coverage','Some delivery orders have no review-view row; inspect the independently governed review population.'))
    return [(a,r) for a,r in choices if a not in done]

async def extend(initial,reader,state):
    result=deepcopy(initial)
    if result.get('executable') is not True or result.get('causal_claim') is not False: return result
    stop='QUESTION_ADDRESSED'
    supporting=[]
    while True:
        try: state.remaining()
        except BudgetStop as exc:
            stop=str(exc)
            break
        choices=candidates(result,state.actions)
        if not choices: break
        action,reason=choices[0]
        try:
            state.begin(action,reason)
            if action=='refund_concentration':
                from agent.refund_concentration import analyze
                proof=await analyze(result['evidence'],reader)
                result['refund_analysis']=deepcopy(proof)
                top=proof['sellers'][0] if proof['sellers'] else None
                conclusion=(f"Seller {top['seller_id']} has the largest exclusive-cohort refund amount: {top['refund_amount']}, or {top['share_of_all_refunds_pct']}% of all linked refunds. {top['returned_orders']} of its {top['orders']} purchased orders have recorded returns." if top and top['refunded_orders'] else 'No positive refund amounts can be attributed to exclusive seller cohorts; return counts and shared or unknown attribution remain available.')
                supporting.append({'capability':action,'evidence_reference':'/payload/refund_analysis','evidence_id':proof['evidence_id'],'conclusion':conclusion})
                state.trace[-1].update(decision='VALIDATED',source=proof['source'])
                continue
            if action=='seller_concentration':
                from agent.seller_concentration import analyze
                proof=await analyze(result['evidence'],reader)
                result['seller_analysis']=deepcopy(proof)
                top=proof['sellers'][0] if proof['sellers'] else None
                conclusion=(f"Seller {top['seller_id']} has the largest observed count: {top['late']} late orders among {top['eligible']} eligible single-seller orders, representing {top['share_of_single_seller_late_pct']}% of single-seller late orders." if top and top['late'] else 'No late orders can be assigned to an exclusive single-seller cohort; shared and unknown orders remain separate.')
                supporting.append({'capability':action,'evidence':deepcopy(proof),'conclusion':conclusion})
                result['limitations']=list(dict.fromkeys([*result.get('limitations',[]),*proof['limitations']]))
                state.trace[-1].update(decision='VALIDATED',source=proof['source'])
                continue
            metric,executor=REGISTRY[action]
            period=result['evidence']['period']
            proof=await executor(metric,*period,reader)
            if proof.get('period')!=period or proof.get('causal_claim') is not False:
                raise ValueError('Supporting evidence contract mismatch')
            if action=='delivery_missingness':
                pop=proof['population']; original=result['evidence']
                classified=sum(original['cohorts'].get(k,{}).get('orders',0) for k in ('late','on_time'))
                if pop['eligible_orders']!=original['total_orders'] or pop['late_orders']!=original['cohorts'].get('late',{}).get('orders',0) or pop['lateness_eligible_orders']!=classified:
                    raise ValueError('Supporting delivery population contradicts initial evidence')
                conclusion=f"Delivery timestamps support classifying {proof['value']}% of this purchase cohort; {pop['missing_actual']} orders lack actual delivery dates and {pop['missing_estimated']} lack promised dates (these counts can overlap)."
            else:
                pop=proof['population']
                conclusion=f"The separate review-source purchase cohort contains {pop['reviewed_orders']} reviewed orders out of {pop['eligible_orders']} ({proof['value']}%). This broader population is not substituted for the delivery comparison denominator."
            supporting.append({'capability':action,'evidence':deepcopy(proof),'conclusion':conclusion})
            state.trace[-1]['decision']='VALIDATED'
            state.trace[-1]['source']=proof['source']
        except (BudgetStop,TimeoutError) as exc:
            stop=str(exc) if isinstance(exc,BudgetStop) else 'DEADLINE_REACHED'
            if state.trace and state.trace[-1]['decision']=='STARTED':state.trace[-1]['decision']='STOPPED'
            break
        except Exception as exc:
            state.trace[-1].update(decision='REJECTED_OR_FAILED',error_type=type(exc).__name__)
            stop='FOLLOWUP_UNAVAILABLE_OR_CONTRADICTORY'
            break
    if supporting:
        result['supporting_analyses']=supporting
        result['conclusions']=list(dict.fromkeys([result.get('reason',''),*result.get('conclusions',[]),*[s['conclusion'] for s in supporting]]))
    if stop!='QUESTION_ADDRESSED':
        result['limitations']=[*result.get('limitations',[]),'The additional investigation could not be completed; earlier validated findings remain available.']
    if result.get('route') not in ('delivery_review_comparison','seller_concentration','refund_concentration'):stop='EXISTING_COORDINATOR_COMPLETED' if 'adaptive' in result else 'NO_RELEVANT_REGISTERED_EXTENSION'
    result['orchestration']=state.snapshot(stop)
    return result
