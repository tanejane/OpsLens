"""Versioned, lossless transport contract; serialization grants no evidence authority.

The payload is the complete executor result, including unknown fields. Status,
scope and validation remain the executor's responsibility. Consumers may project
summaries but must retain this record for technical inspection and export.
"""
from copy import deepcopy
from decimal import Decimal
import math
from contextlib import contextmanager
from contextvars import ContextVar
from functools import wraps

SCHEMA_VERSION = "opslens.investigation.v1"
_archive = ContextVar('investigation_evidence_archive', default=None)


@contextmanager
def evidence_archive():
    """Request-local completed proofs, including when a later step fails."""
    entries = []
    token = _archive.set(entries)
    try:
        yield entries
    finally:
        _archive.reset(token)


def retain_validated(validator):
    """Record only successful validator returns; never change validation behavior."""
    @wraps(validator)
    def wrapped(*args, **kwargs):
        result = validator(*args, **kwargs)
        entries = _archive.get()
        if entries is not None:
            entries.append({'producer': validator.__module__ + '.' + validator.__name__,
                            'result': deepcopy(result)})
        return result
    return wrapped


def canonical_result(question, result):
    if not isinstance(result, dict):
        raise TypeError("Investigation result must be an object")
    number_encodings = {}
    def transport(value, path):
        if isinstance(value, Decimal) or type(value) is int and abs(value) > 2**53 - 1:
            if isinstance(value, Decimal) and not value.is_finite():
                raise ValueError('Nonfinite evidence number')
            number_encodings[path] = 'decimal' if isinstance(value, Decimal) else 'integer'
            return str(value)
        if isinstance(value, float) and not math.isfinite(value):
            raise ValueError('Nonfinite evidence number')
        if isinstance(value, dict):
            return {key: transport(item, path + '/' + key.replace('~', '~0').replace('/', '~1')) for key, item in value.items()}
        if isinstance(value, (list, tuple)):
            return [transport(item, path + '/' + str(index)) for index, item in enumerate(value)]
        return deepcopy(value)
    record = {"schema_version": SCHEMA_VERSION, "question": question,
              "payload": transport(result, '/payload')}
    if number_encodings:
        record['number_encodings'] = number_encodings
    return record


def investigation_response(question, result):
    record = canonical_result(question, result)
    # Presentation-only Trace V2 projection of the recorded execution streams.
    # The original source traces remain unchanged in the canonical record.
    # This entry point is used by stateless and session-backed API turns.
    from agent.trace_projection import project_agent_trace
    record["payload"]["agent_trace_v2"] = project_agent_trace(record["payload"])
    # Retain the legacy field for existing clients during the v1 transition.
    return {"question": question, "result": record["payload"], "canonical_result": record}
