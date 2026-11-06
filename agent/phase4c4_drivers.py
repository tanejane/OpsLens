"""Governed cost-driver reconciliation for Phase 4C.3 investigations.

Uses a fixed SQL template on an explicitly migrated semantic view. Never executes
LLM-written SQL, reads staging, creates schema objects, or declares causality.
"""
from __future__ import annotations
from agent.investigation_result import retain_validated
from decimal import Decimal, InvalidOperation
from agent.phase4b56_dynamic_period import requested_period

SOURCE = 'semantic.order_cost_components'
COMPONENTS = ('refund_amount', 'fulfillment_cost', 'payment_processing_cost',
              'marketing_cost_effective', 'incentive_cost_effective',
              'other_adjustments_residual')
TOTALS = ('effective_revenue', 'effective_cogs', 'effective_contribution_profit')
FIELDS = TOTALS + COMPONENTS

class DriverRejected(ValueError):
    pass

def as_decimal(value):
    try:
        v = Decimal(str(value))
        if not v.is_finite():
            raise DriverRejected('Non-finite observed component')
        return v
    except (InvalidOperation, TypeError, ValueError) as exc:
        raise DriverRejected('Invalid observed component') from exc

def compile_components(start: str, end: str) -> str:
    period = requested_period(start, end)
    sums = ', '.join(f'SUM(t0."{col}") AS "{col}"' for col in FIELDS)
    return (f'SELECT COUNT(*) AS eligible_source_rows, '
            f'COUNT(DISTINCT t0."order_id") AS distinct_orders, {sums} '
            f'FROM "semantic"."order_cost_components" t0 '
            f'WHERE t0."order_purchase_timestamp"::timestamp >= DATE \'{period.start}\' '
            f'AND t0."order_purchase_timestamp"::timestamp < DATE \'{period.end}\' LIMIT 1')

@retain_validated
def validate_components(response: dict, period: tuple[str, str], expected: dict,
                        tolerance: Decimal=Decimal('0.05')) -> dict:
    if not isinstance(response,dict) or response.get('ok') is False:
        raise DriverRejected('MCP did not return an approved component measurement')
    rows = response.get('rows')
    if not isinstance(rows,list) or len(rows)!=1 or not isinstance(rows[0],dict):
        raise DriverRejected('Exactly one aggregate row required')
    row=rows[0]
    try:
        n=int(row['eligible_source_rows'])
        unique=int(row['distinct_orders'])
    except (KeyError, TypeError, ValueError) as exc:
        raise DriverRejected('Missing component population') from exc
    if n<=0 or unique!=n:
        raise DriverRejected('Empty or duplicate order-grain component population')
    try:
        data={name:as_decimal(row[name]) for name in FIELDS}
    except KeyError as exc:
        raise DriverRejected('Required component field missing') from exc
    for col in TOTALS:
        proof=expected.get(col)
        if not isinstance(proof,dict) or proof.get('source')!='semantic.order_economics' or proof.get('period')!=list(period) or proof.get('status')!='MEASURED_WITH_SCOPE_LIMITS' or proof.get('period_reconciliation_status')!='RECONCILED_FOR_REVIEW':
            raise DriverRejected('Missing independently reconciled finance measurement')
        if n!=int(proof.get('source_population_rows',-1)):
            raise DriverRejected('Component population differs from audited finance population')
        if abs(data[col]-as_decimal(proof.get('value'))) > tolerance:
            raise DriverRejected('Component totals do not reconcile to audited finance totals: '+col)
    lhs=data['effective_revenue']-data['effective_cogs']-data['effective_contribution_profit']
    rhs=sum((data[k] for k in COMPONENTS), Decimal(0))
    if abs(lhs-rhs)>tolerance:
        raise DriverRejected('Component-level cost identity does not balance')
    return {'source':SOURCE,'period':list(period),'source_population_rows':n,
            'components':{k:str(data[k]) for k in COMPONENTS},
            'reconciliation':'RECONCILED_FOR_REVIEW','causal_claim':False}

def _proofs(core:dict, moment:str)->dict:
    evidence=core.get('evidence',{})
    return {k:evidence.get(k,{}).get(moment) for k in TOTALS}

async def discover_drivers(core:dict, reader, *, tolerance=Decimal('0.05')) -> dict:
    """Augment a successful 4C.3 result; never silently treat missing data as zero.

    reader(sql, purpose) is the existing read-only MCP query adapter.
    """
    if core.get('route')!='investigation' or core.get('executable') is not True or core.get('causal_claim') is not False:
        raise DriverRejected('Prior investigation is not eligible')
    periods=core.get('periods',{})
    observations={}
    try:
        for moment in ('before','after'):
            dates=periods[moment]
            period=requested_period(*dates)
            sql=compile_components(period.start,period.end)
            raw=await reader(sql, 'governed cost component reconciliation: '+moment)
            observations[moment]=validate_components(raw,(period.start,period.end),_proofs(core,moment),tolerance)
        b=observations['before']['components']; a=observations['after']['components']
        changes={k:as_decimal(a[k])-as_decimal(b[k]) for k in COMPONENTS}
        total=sum(changes.values(),Decimal(0))
        original=next((f for f in core.get('findings',[]) if f.get('component')=='other_net_charges_residual'),None)
        if not original or abs(total-as_decimal(original['delta']))>tolerance:
            raise DriverRejected('Driver deltas do not reconcile to original investigation bridge')
        return {**core,'driver_discovery':{
            'status':'RECONCILED_COMPONENT_BREAKDOWN','source':SOURCE,'causal_claim':False,
            'components':[
                {'component':k,'before':b[k],'after':a[k],'delta':str(changes[k]),
                 'contribution_to_profit_delta':str(-changes[k])} for k in COMPONENTS],
            'total_other_net_charges_delta':str(total),
            'period_evidence':observations,
            'limitations':['Accounting contribution is not causal identification',
                           'Costs and incident adjustments are partly synthetic or modeled',
                           'Other adjustments are a balancing residual, not a known causal mechanism',
                           'No dimension/category allocations or joins have been approved',
                           'Nonempty period coverage does not establish continuous completeness']}}
    except (DriverRejected, KeyError, TypeError, ValueError) as exc:
        return {**core,'driver_discovery':{'status':'DRIVER_EVIDENCE_UNAVAILABLE',
            'period_evidence':observations,
            'reason':str(exc)[:250], 'causal_claim':False,
            'limitations':['The original 4C.3 accounting bridge remains descriptive and valid',
                           'No component-level claim can be made without a reconciled semantic view']}}
