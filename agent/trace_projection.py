"""Non-executable, source-local projection of recorded OpsLens agent events.

This is display metadata only. No new tool, metric, or SQL permission is granted.
A cross-stream chronological sequence cannot be established from these inputs.
"""

from typing import Any


def _object(value: Any) -> dict:
    return value if isinstance(value, dict) else {}


def _records(value: Any) -> list:
    return value if isinstance(value, list) else []


def _string(value: Any) -> str | None:
    return value if isinstance(value, str) and value.strip() else None


def _duration(value: Any) -> float | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)) and 0 <= value < float('inf'):
        return float(value)
    return None


def project_agent_trace(payload: dict) -> dict:
    """Preserve stream-local indexes, including skipped/malformed events.

    Do not copy SQL text, arbitrary reasons from tool arguments, tool responses,
    unverified evidence references, or model-proposed code into this projection.
    """
    payload = _object(payload)
    finance = _object(_object(payload.get('domain_results')).get('finance'))
    streams = [
        ('orchestration', _records(_object(payload.get('orchestration')).get('trace'))),
        ('adaptive', _records(_object(payload.get('adaptive')).get('trace'))),
        ('finance_adaptive', _records(_object(finance.get('adaptive')).get('trace'))),
        ('execution', _records(payload.get('execution_trace'))),
    ]
    events = []
    for source, records in streams:
        for index, value in enumerate(records):
            entry = _object(value)
            if not entry:
                continue
            tool = _string(entry.get('tool'))
            capability = _string(entry.get('capability'))
            decision = _string(entry.get('decision'))
            if tool:
                event = {
                    'id': f'{source}:{index}', 'source': source,
                    'source_index': index, 'stage': 'tool_execution',
                    'tool': tool,
                    'outcome': _string(entry.get('outcome')),
                    'latency_ms': _duration(entry.get('latency_ms')),
                    'error_type': _string(entry.get('error_type')),
                }
            elif capability or decision:
                event = {
                    'id': f'{source}:{index}', 'source': source,
                    'source_index': index, 'stage': 'decision',
                    'capability': capability, 'decision': decision,
                    'reason': _string(entry.get('reason')),
                }
            else:
                continue
            events.append(event)

    stops = []
    for source, value in (
        ('orchestration', payload.get('orchestration')),
        ('adaptive', payload.get('adaptive')),
        ('finance_adaptive', finance.get('adaptive')),
    ):
        reason = _string(_object(value).get('stop_reason'))
        if reason:
            stops.append({'id': f'{source}:stop', 'source': source, 'stage': 'stop', 'reason': reason})

    observability = _object(payload.get('observability'))
    return {
        'schema_version': 'opslens.agent_trace.v2',
        'ordering': 'SOURCE_LOCAL_ONLY',
        'global_sequence_verified': False,
        'events': events,
        'stop_conditions': stops,
        'validation_decision': _string(observability.get('validation_decision')),
        'raw_execution_excluded': True,
    }
