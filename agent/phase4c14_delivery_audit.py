"""Phase 4C.14 audit gate: no MCP metric authorization; deterministic fail-closed evidence checks."""
from decimal import Decimal, InvalidOperation

COUNTS = ('orders','unique_orders','null_keys','missing_actual','missing_estimated','missing_purchase',
          'lateness_eligible','late_orders','duration_eligible','negative_duration')

def _count(x, key):
    value = x.get(key)
    if type(value) is not int or value < 0:
        raise ValueError(f'Invalid or missing count {key}')
    return value

def _average(value):
    if value is None:
        return None
    try:
        n = Decimal(str(value))
    except (InvalidOperation, ValueError):
        raise ValueError('Invalid mean delivery days') from None
    if not n.is_finite() or n < 0:
        raise ValueError('Invalid mean delivery days')
    return n

def assess(audit):
    if not isinstance(audit, dict) or any((
        audit.get('audit_version') != '4c14.1',
        audit.get('source') != 'operations.delivery_effective',
        audit.get('view') != 'semantic.order_delivery_evidence_v1',
        audit.get('policy') != 'late_iff_actual_gt_estimated_on_eligible_orders',
        audit.get('time_basis') != 'order_purchase_time',
        audit.get('read_only') is not True,
        audit.get('mcp_approved') is not False,
    )):
        raise ValueError('Untrusted audit contract')
    raw, derived, monthly = (audit.get(k) for k in ('raw','derived','monthly'))
    if not all(isinstance(v, dict) for v in (raw,derived,monthly)):
        raise ValueError('Missing audit evidence')
    for data in (raw,derived):
        for key in COUNTS: _count(data,key)
        orders = data['orders']
        for key in COUNTS[1:]:
            if data[key] > orders: raise ValueError(f'Impossible count {key}')
        if data['late_orders'] > data['lateness_eligible'] or data['duration_eligible'] + data['negative_duration'] > orders:
            raise ValueError('Impossible eligible population')
        if _average(data.get('mean_delivery_days')) is None and data['duration_eligible'] > 0:
            raise ValueError('Mean absent for eligible deliveries')
    for key in ('invalid_late_flags','invalid_duration_values','missing_eligible_flags','missing_eligible_duration'):
        _count(derived,key)
    for key in ('month_rows','distinct_months','missing_purchase_rows'):
        _count(monthly,key)
    if monthly['distinct_months'] > monthly['month_rows']:
        raise ValueError('Impossible monthly count')
    failures=[]; warnings=[]
    if raw['orders'] == 0: failures.append('EMPTY_DELIVERY_SOURCE')
    if raw['null_keys'] or derived['null_keys'] or raw['unique_orders'] != raw['orders'] or derived['unique_orders'] != derived['orders']:
        failures.append('ORDER_GRAIN_INVALID')
    for key in COUNTS:
        if raw[key] != derived[key]: failures.append(f'RAW_VIEW_MISMATCH:{key}')
    if monthly['month_rows'] != derived['orders'] or monthly['missing_purchase_rows'] != derived['missing_purchase']:
        failures.append('MONTHLY_POPULATION_MISMATCH')
    for key in ('invalid_late_flags','invalid_duration_values','missing_eligible_flags','missing_eligible_duration'):
        if derived[key]: failures.append(key.upper())
    if raw['negative_duration']: failures.append('NEGATIVE_DELIVERY_DURATION')
    ra,va = _average(raw.get('mean_delivery_days')), _average(derived.get('mean_delivery_days'))
    if ra != va: failures.append('MEAN_DELIVERY_RECONCILIATION_FAILED')
    for key in ('missing_actual','missing_estimated','missing_purchase'):
        if raw[key]: warnings.append(key.upper())
    warnings.append('AUDIT_ONLY_MCP_NOT_AUTHORIZED')
    return {'status':'DELIVERY_EVIDENCE_AUDIT_PASSED' if not failures else 'DELIVERY_EVIDENCE_AUDIT_BLOCKED',
            'failures':failures,'warnings':warnings,
            'counts':{key:raw[key] for key in COUNTS},
            'purchase_months':monthly['distinct_months'],
            'mean_delivery_days':str(ra) if ra is not None else None,
            'approved_for_mcp':False,'causal_claim':False,
            'next_gate':'Validate monthly metric denominators, role privileges and the MCP allowlist before execution.'}
