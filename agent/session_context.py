"""Narrow contextual slots over RecoverySession, not free-form model memory."""
from copy import deepcopy
from datetime import date
import re
from agent.phase4c25_clarification import MONTHS, CANCEL
from agent.phase4c26_recovery import CORRECTION
from agent.phase5_1_unified import SUSPICIOUS

MONTH = r'(' + '|'.join(MONTHS) + r')(?:\s+(20\d{2}))?'
METRICS = {'profit':'effective_contribution_profit', 'contribution profit':'effective_contribution_profit',
           'revenue':'effective_revenue', 'cogs':'effective_cogs', 'contribution margin':'effective_contribution_margin_pct',
           'gross margin':'effective_gross_margin_pct','placed orders':'placed_orders','financially represented orders':'financially_represented_orders'}
OPERATIONS = {'late_delivery_rate':'late delivery rate','average_delivery_days':'average delivery days',
    'delivery_evidence_coverage':'delivery evidence coverage','delivered_order_count':'delivered order count',
    'average_review_score':'average review score','low_rating_rate':'low rating rate','review_coverage':'review coverage'}


def safe(question):
    return bool(question.strip()) and not (SUSPICIOUS.search(question) or ';' in question)


def period(month, year):
    m = MONTHS.index(month.lower()) + 1
    y = int(year)
    if not 2016 <= y <= 2026: raise ValueError('Unsupported year')
    return [date(y,m,1).isoformat(),date(y+(m==12),m%12+1,1).isoformat()]


def slots(record):
    if not record: return {}
    result = record['payload']
    evidence = result.get('evidence', {})
    measurement = evidence.get('measurement', evidence)
    current = measurement.get('period') or result.get('periods', {}).get('after') or result.get('after', {}).get('period')
    metric = evidence.get('metric_id') or result.get('metric_id')
    periods = [current,evidence.get('before',{}).get('period'),result.get('periods',{}).get('before'),result.get('before',{}).get('period')]
    years = sorted({p[0][:4] for p in periods if isinstance(p,list) and p and isinstance(p[0],str)})
    return {'period':current, 'metric':metric, 'route':result.get('route'),'years':years,'refund_intent':result.get('refund_intent',False)}


def clarification(reason):
    return {'route':'session_context','status':'NEEDS_CLARIFICATION','executable':False,
            'causal_claim':False,'reason':reason}


def resolve(question, recovery, last_valid):
    """Return (canonical question, server-only action, immediate result, provenance).

    Only explicit user slots or a single established reporting year are inherited.
    All other requests use the existing recovery/Gemini routing unchanged.
    """
    q = question.strip().rstrip('?.! ').strip()
    known = slots(last_valid)
    pending = deepcopy(recovery.investigation_pending) or {}
    provenance = {'original_question':question, 'policy':'bounded_session_slots_v1', 'inherited':[]}
    if not safe(q): return question, None, None, provenance
    if CANCEL.fullmatch(q):
        recovery.pending = None
        recovery.investigation_pending = None
        return question, None, {'route':'language_clarification','status':'CANCELLED','executable':False,
            'causal_claim':False,'inventory_claim_allowed':False}, provenance
    if re.fullmatch(r'(?:check|cross.check|corroborate) (?:that|this|those findings|these findings)(?: against| with| using)? (?:the |business )?(?:documents|notes|reports)|what do (?:the |business )?documents say(?: about (?:that|this))?',q,re.I):
        if not last_valid:return question,None,clarification('First establish a governed measurement, then ask to cross-check it against documents.'),provenance
        provenance['inherited'].append({'field':'database_record','source':'last_validated_result'})
        return question,{'kind':'document_corroboration','record':deepcopy(last_valid)},None,provenance
    from agent.refund_routing import contextual as refund_context
    refund=refund_context(q,known,pending)
    if refund is not None:
        action,immediate,inherited=refund
        provenance['inherited'].extend(inherited)
        recovery.investigation_pending={'capability':'refund_concentration','question':q,'detail':bool(re.search(r'concentrat|sellers?|break.?down|where|why|which',q,re.I))} if immediate and immediate.get('status')=='NEEDS_CLARIFICATION' else None
        return question,action,immediate,provenance
    from agent.seller_routing import contextual as seller_context
    seller = seller_context(q,known,pending)
    if seller is not None:
        action,immediate,inherited=seller
        provenance['inherited'].extend(inherited)
        recovery.investigation_pending={'capability':'seller_concentration','question':q} if immediate and immediate.get('status')=='NEEDS_CLARIFICATION' else None
        return question,action,immediate,provenance
    from agent.delivery_review_routing import contextual
    comparison = contextual(q,known,pending,last_valid)
    if comparison is not None:
        action, immediate, inherited = comparison
        provenance['inherited'].extend(inherited)
        recovery.investigation_pending = {'capability':'delivery_review_comparison','question':q} if immediate and immediate.get('status')=='NEEDS_CLARIFICATION' else None
        return question,action,immediate,provenance
    why = re.fullmatch(r'why did (?:contribution )?profit (?:decline|fall|decrease) in '+MONTH, q, re.I)
    compare = re.fullmatch(r'compare (?:that|it) with '+MONTH, q, re.I)
    correction = CORRECTION.match(q)
    chosen = re.fullmatch(MONTH, CORRECTION.sub('',q,count=1) if correction else q, re.I)
    follow = re.fullmatch(r'(?:what|how) about '+MONTH,q,re.I)
    if follow: chosen = follow
    if recovery.pending is not None and not why:
        # Sales/category clarification remains owned by the existing recovery
        # component, even if an older validated finance result also exists.
        if correction and chosen and chosen.group(2) is None and recovery.pending.period:
            anchor = re.fullmatch(MONTH,recovery.pending.period,re.I)
            if anchor and anchor.group(2):
                canonical = f'No, I meant {chosen.group(1).capitalize()} {anchor.group(2)}'
                provenance['resolved_question'] = canonical
                provenance['inherited'].append({'field':'year','value':anchor.group(2),'source':'legacy_clarification'})
                return canonical,{'kind':'recovery'},None,provenance
        return question,None,None,provenance
    metric_choice = METRICS.get(CORRECTION.sub('',q,count=1).strip().lower()) if pending else None
    if re.fullmatch(r'(?:break down|breakdown) marketing (?:expenses|costs|spend)(?: further)?',q,re.I):
        proofs = []
        def visit(value, path):
            if isinstance(value,dict):
                if value.get('component') == 'marketing_cost_effective' or value.get('hypothesis_id') == 'financial_component:marketing_cost_effective':
                    proofs.append({'reference':path,'evidence':deepcopy(value)})
                else:
                    for key, item in value.items():
                        if key not in ('stage_results','metric_results','validated_evidence'):
                            visit(item,path+'/'+key)
            elif isinstance(value,list):
                for index,item in enumerate(value): visit(item,path+'/'+str(index))
        if last_valid: visit(last_valid['payload'],'/payload')
        return question,None,{'route':'session_context','status':'ACTIONABLE_EVIDENCE_GAP','executable':False,'causal_claim':False,
            'reason':('The retained marketing accounting movements and per-order context are shown as supporting evidence. ' if proofs else 'No validated marketing breakdown is retained for this investigation. ')
                + 'Campaign/channel breakdown and causal attribution are not governed capabilities.',
            'supporting_evidence':proofs,'source_result':deepcopy(last_valid) if proofs else None,
            'evidence_requirements':['Separately governed campaign/channel expense evidence and attribution controls'],
            'limitations':['No deeper marketing breakdown was executed; retained accounting evidence does not establish causes']},provenance
    if not (why or compare or chosen and (pending or correction or follow) or metric_choice):
        if pending and not re.search(r'\b(?:revenue|profit|margin|cogs|sales|delivery|reviews?|ratings?|products?|sellers?|stock|inventory|marketing)\b',q,re.I):
            return question,None,clarification('A finance comparison is pending. Specify the baseline month, correct the reporting period, or cancel.'),provenance
        # An explicit new topic supersedes pending slots on a successful turn.
        recovery.investigation_pending = None
        return question,None,None,provenance
    base = pending or known
    if metric_choice:
        pending['metric'] = metric_choice
        recovery.investigation_pending = pending
        if not pending.get('baseline'):
            return question,None,clarification('Which baseline month and year should I compare?'),provenance
        target = pending['baseline']
    else:
        match = why or compare or chosen
        month, year = match.groups()
        if year is None:
            anchor = base.get('period')
            if not anchor or len(base.get('years',[])) > 1:
                return question,None,clarification('Which year? No unambiguous reporting year is established.'),provenance
            year = anchor[0][:4]
            provenance['inherited'].append({'field':'year','value':year,'source':'pending_request' if pending else 'last_validated_result'})
        try: target = period(month,year)
        except ValueError:
            return question,None,clarification('Specify a supported month and year.'),provenance
    if why:
        recovery.pending = None
        recovery.investigation_pending = {'period':target,'metric':'effective_contribution_profit','intent':'profit_comparison'}
        return question,None,clarification('Compared with which month? I can measure contribution-profit changes; a decline alone does not establish its cause.'),provenance
    if not pending and known.get('route') in ('graph_analytics','product_category'):
        if compare:
            return question,None,{'route':'session_context','status':'ACTIONABLE_EVIDENCE_GAP','executable':False,'causal_claim':False,
                'reason':'An implicit comparison for this graph/product result is not a registered capability. Specify a supported measurement or ranking.',
                'evidence_requirements':['A separately governed comparison contract for this metric and dimensions']},provenance
        canonical = f'What about {MONTHS[int(target[0][5:7])-1].capitalize()} {target[0][:4]}?'
        provenance['resolved_question'] = canonical
        return canonical,{'kind':'recovery'},None,provenance
    if known.get('metric') in OPERATIONS and not pending:
        def name(p): return MONTHS[int(p[0][5:7])-1].capitalize()+' '+p[0][:4]
        label = OPERATIONS[known['metric']]
        if compare:
            current = known.get('period')
            if not current or current == target:
                return question,None,clarification('Choose a distinct reporting period to compare.'),provenance
            canonical = f'Compare {label} from {name(min(current,target))} to {name(max(current,target))}'
        else: canonical = f'What was the {label} in {name(target)}?'
        provenance['resolved_question'] = canonical
        provenance['inherited'].append({'field':'metric','value':known['metric'],'source':'last_validated_result'})
        return canonical,{'kind':'recovery'},None,provenance
    if correction and pending and not metric_choice:
        pending['period'] = target
        pending.pop('baseline',None)
        recovery.investigation_pending = pending
        return question,None,clarification('Reporting period corrected. Which baseline month should I compare?'),provenance
    if (correction or follow) and not pending:
        metric = known.get('metric')
        if metric not in METRICS.values():
            return question,None,clarification('Which governed metric should use the corrected period?'),provenance
        action = {'kind':'finance','metric':metric,'before':None,'after':target}
    else:
        current = base.get('period')
        metric = base.get('metric')
        if not current:
            return question,None,clarification('Which current metric and reporting period should I compare?'),provenance
        if metric not in METRICS.values():
            recovery.investigation_pending = {'period':current,'baseline':target}
            return question,None,clarification('Which finance metric: contribution profit, revenue, COGS, or contribution margin? Other domain comparisons require an explicit supported request.'),provenance
        if target == current:
            return question,None,clarification('Choose a different baseline period.'),provenance
        if pending.get('intent') == 'profit_comparison' and target > current:
            return question,None,clarification('Choose a baseline before the requested decline period.'),provenance
        action = {'kind':'finance','metric':metric,'before':min(current,target),'after':max(current,target)}
    provenance['inherited'].append({'field':'metric','value':action['metric'],'source':'pending_request' if pending else 'last_validated_result'})
    recovery.investigation_pending = None
    label = next(key for key,value in METRICS.items() if value == action['metric'])
    def name(p): return MONTHS[int(p[0][5:7])-1].capitalize()+' '+p[0][:4]
    canonical = (f'Compare {label} from {name(action["before"])} to {name(action["after"])}' if action['before'] else f'What was {label} in {name(action["after"])}?')
    provenance['resolved_question'] = canonical
    return canonical,action,None,provenance
