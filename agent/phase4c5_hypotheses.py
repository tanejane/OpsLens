"""Phase 4C.5: governed, evidence-driven hypothesis evaluation.

Pure post-processing of a reconciled Phase 4C.4 investigation. Does not query
MCP, accept LLM SQL, load fixture ground truth, or infer causation.
"""
from __future__ import annotations
from decimal import Decimal, InvalidOperation

CHARGE_FIELDS = frozenset({
    'refund_amount', 'fulfillment_cost', 'payment_processing_cost',
    'marketing_cost_effective', 'incentive_cost_effective',
    'other_adjustments_residual',
})
LABELS = {
    'effective_cogs': 'Cost of goods sold',
    'marketing_cost_effective': 'Marketing expense',
    'refund_amount': 'Refund expense',
    'incentive_cost_effective': 'Campaign incentives',
    'fulfillment_cost': 'Fulfillment expense',
    'payment_processing_cost': 'Payment processing expense',
    'other_adjustments_residual': 'Unresolved financial adjustments',
}
UNTESTED = {
    'campaign_incrementality': 'Marketing spend alone cannot establish incremental campaign return',
    'product_mix': 'Item-level financial allocations are not governed for product/category profit',
    'customer_cohorts': 'No verified cohort-level contribution-profit evidence provided',
    'operational_causation': 'Accounting movement does not identify the operational cause',
}

class HypothesisRejected(ValueError):
    pass


def dec(value):
    try:
        d = Decimal(str(value))
    except (InvalidOperation, ValueError, TypeError) as exc:
        raise HypothesisRejected('Invalid numeric evidence') from exc
    if not d.is_finite():
        raise HypothesisRejected('Non-finite numeric evidence')
    return d


def _expected_core(out):
    if not isinstance(out, dict) or out.get('route') != 'investigation' or out.get('executable') is not True or out.get('causal_claim') is not False:
        raise HypothesisRejected('Unsupported core investigation')
    premise=out.get('premise', {})
    if not isinstance(premise,dict):
        raise HypothesisRejected('Missing premise evidence')
    rp=dec(premise['revenue_delta']); pp=dec(premise['contribution_profit_delta'])
    if (rp>0) != premise.get('revenue_increased') or (pp<0) != premise.get('contribution_profit_decreased') or (rp>0 and pp<0) != premise.get('divergence_confirmed'):
        raise HypothesisRejected('Premise contradicts signed measurements')
    findings=out.get('findings')
    if not isinstance(findings,list) or len(findings)!=3 or {f.get('component') for f in findings} != {'effective_revenue','effective_cogs','other_net_charges_residual'}:
        raise HypothesisRejected('Incomplete accounting bridge')
    fm={f['component']:f for f in findings}
    rev=dec(fm['effective_revenue']['delta']); cogs=dec(fm['effective_cogs']['delta']); other=dec(fm['other_net_charges_residual']['delta'])
    for k,impact in (('effective_revenue',rev),('effective_cogs',-cogs),('other_net_charges_residual',-other)):
        if abs(dec(fm[k]['contribution_to_profit_delta'])-impact)>Decimal('0.05'):
            raise HypothesisRejected('Bridge contribution sign mismatch')
    if abs(rev-rp)>Decimal('0.05') or abs(rev-cogs-other-pp)>Decimal('0.05'):
        raise HypothesisRejected('Accounting bridge does not reconcile')
    return pp,cogs,other


def evaluate_hypotheses(out:dict, *, max_hypotheses:int=5, tolerance=Decimal('0.05')) -> dict:
    """Evaluate verified component movements, not causal mechanisms.

    Strictly cross-checks independently reconciled periods, row counts, delta
    identities, population scope and the core bridge before ranking evidence.
    """
    if isinstance(max_hypotheses,bool) or not isinstance(max_hypotheses,int) or not 1<=max_hypotheses<=7:
        raise HypothesisRejected('Invalid hypothesis budget')
    profit_delta,cogs_delta,other_delta=_expected_core(out)
    discovery=out.get('driver_discovery')
    if not isinstance(discovery,dict) or discovery.get('status')!='RECONCILED_COMPONENT_BREAKDOWN':
        return {'status':'INSUFFICIENT_GOVERNED_EVIDENCE','causal_claim':False,'hypotheses':[],
                'reason':'Reconciled cost-component evidence is unavailable', 'untested':UNTESTED.copy()}
    if discovery.get('source')!='semantic.order_cost_components' or discovery.get('causal_claim') is not False:
        raise HypothesisRejected('Wrong source or causal assertion in driver evidence')
    periods=out.get('periods')
    proofs=discovery.get('period_evidence')
    if not isinstance(periods,dict) or not isinstance(proofs,dict):
        raise HypothesisRejected('Missing period provenance')
    observed={}
    for which in ('before','after'):
        e=proofs.get(which)
        if not isinstance(e,dict) or e.get('source')!='semantic.order_cost_components' or e.get('causal_claim') is not False or e.get('reconciliation')!='RECONCILED_FOR_REVIEW' or e.get('period')!=periods.get(which):
            raise HypothesisRejected('Invalid component evidence provenance')
        n=e.get('source_population_rows')
        if isinstance(n,bool) or not isinstance(n,int) or n<=0:
            raise HypothesisRejected('Invalid source population')
        core_evidence=out.get('evidence',{})
        for metric in ('effective_revenue','effective_cogs','effective_contribution_profit'):
            row=core_evidence.get(metric,{}).get(which)
            if not isinstance(row,dict) or row.get('source')!='semantic.order_economics' or row.get('period')!=periods.get(which) or row.get('status')!='MEASURED_WITH_SCOPE_LIMITS' or row.get('period_reconciliation_status')!='RECONCILED_FOR_REVIEW' or row.get('source_population_rows')!=n:
                raise HypothesisRejected('Population or period inconsistent with audited finance')
        components=e.get('components')
        if not isinstance(components,dict) or set(components)!=CHARGE_FIELDS:
            raise HypothesisRejected('Unexpected component contract')
        observed[which]={k:dec(v) for k,v in components.items()}
    records=discovery.get('components')
    if not isinstance(records,list) or len(records)!=len(CHARGE_FIELDS):
        raise HypothesisRejected('Invalid component records')
    indexed={}
    for record in records:
        if not isinstance(record,dict) or record.get('component') not in CHARGE_FIELDS or record['component'] in indexed:
            raise HypothesisRejected('Duplicate or unknown component')
        key=record['component']
        before=observed['before'][key]; after=observed['after'][key]; delta=after-before
        if (abs(dec(record['before'])-before)>tolerance or abs(dec(record['after'])-after)>tolerance or
            abs(dec(record['delta'])-delta)>tolerance or abs(dec(record['contribution_to_profit_delta'])+delta)>tolerance):
            raise HypothesisRejected('Component delta mismatch')
        indexed[key]=delta
    if set(indexed)!=CHARGE_FIELDS or abs(sum(indexed.values(),Decimal(0))-other_delta)>tolerance or abs(dec(discovery.get('total_other_net_charges_delta'))-other_delta)>tolerance:
        raise HypothesisRejected('Driver breakdown fails accounting reconciliation')
    # COGS belongs to the core audited bridge, not the cost-components view.
    movements=[('effective_cogs',cogs_delta)]+sorted(indexed.items())
    ranked=sorted(movements,key=lambda x:(-abs(x[1]),x[0]))
    hypotheses=[]
    for key,delta in ranked[:max_hypotheses]:
        impact=-delta
        if abs(delta)<=tolerance:
            disposition='NO_MATERIAL_CHANGE'
        elif impact < 0:
            disposition='SUPPORTS_PROFIT_PRESSURE'
        elif impact > 0:
            disposition='COUNTERACTS_PROFIT_PRESSURE'
        else:
            disposition='NO_MATERIAL_CHANGE'
        hypotheses.append({
            'hypothesis_id':'financial_component:'+key,
            'label':LABELS[key], 'observed_cost_change':str(delta),
            'accounting_profit_impact':str(impact), 'disposition':disposition,
            'evidence_type':'reconciled_accounting_contribution',
            'source':('semantic.order_economics' if key=='effective_cogs' else 'semantic.order_cost_components'),
            'causal_claim':False,
            'next_validation':('Verify attribution mechanism using independent operational data' if key!='other_adjustments_residual' else 'Residual is not an independently measured business activity'),
        })
    return {
        'status':'EVIDENCE_RANKED_NOT_CAUSAL',
        'causal_claim':False,
        'premise_confirmed':out['premise']['divergence_confirmed'],
        'profit_delta':str(profit_delta),
        'hypotheses':hypotheses,
        'hypotheses_evaluated':len(movements),
        'hypotheses_returned':len(hypotheses),
        'untested':UNTESTED.copy(),
        'limitations':[
            'Ranks measured accounting movements, not causal root causes',
            'Financial data include modeled or synthetic cost components',
            'No cross-domain joins, cohort comparisons, or statistical causal tests were performed',
            'Only the supplied two periods were evaluated; completeness across all dates is not certified',
        ],
    }
