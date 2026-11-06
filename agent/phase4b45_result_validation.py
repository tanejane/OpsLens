"""Phase 4B.4.5: conservative evidence/result validation for graph analyses.

This module never decides SQL joins, creates metrics, or interprets causes.
"""
from __future__ import annotations
from dataclasses import dataclass, asdict
from datetime import date
from typing import Any
from agent.phase4b43_graph_planner import date_expr, table, ident, AnalysisRequest

class EvidenceUnavailable(ValueError):
    pass

@dataclass(frozen=True)
class EvidenceAssessment:
    status: str
    message: str
    observations: list[str]
    can_save_context: bool


def coverage_probe(plan: dict, req: AnalysisRequest, semantic_map) -> str:
    """Generate a *separate* read-only source availability query; not a metric result.

    Uses the same canonical date source as the metric compiler. Explicit source-grain
    verification is still required by the planner; this does not authorize joins.
    """
    source = semantic_map.metrics[req.metric]['source']
    src = semantic_map.sources[source]
    date_col = src.get('date_column')
    if not date_col:
        raise EvidenceUnavailable('Metric source has no date contract')
    lo = date.fromisoformat(req.start_date)
    hi = date.fromisoformat(req.end_date_exclusive)
    if lo >= hi:
        raise EvidenceUnavailable('Invalid period')
    expression = date_expr('t0', date_col)
    return (f'SELECT COUNT(*) AS eligible_source_rows FROM {table(source)} t0 '
            f"WHERE {expression} >= DATE '{lo.isoformat()}' "
            f"AND {expression} < DATE '{hi.isoformat()}' LIMIT 1")


def _count(probe_result: dict) -> int | None:
    if not isinstance(probe_result, dict) or not isinstance(probe_result.get('rows'), list):
        return None
    rows = probe_result['rows']
    if len(rows) != 1 or not isinstance(rows[0], dict):
        return None
    raw = rows[0].get('eligible_source_rows')
    if isinstance(raw, bool):
        return None
    try:
        value = int(raw)
        if value < 0 or str(raw).strip() not in (str(value),):
            return None
        return value
    except (ValueError, TypeError):
        return None


def assess_result(req: AnalysisRequest, plan: dict, probe_result: dict, metric_result: dict) -> EvidenceAssessment:
    """No claims of zero from empty rows, nulls, malformed response or failed probes."""
    n = _count(probe_result)
    if n is None:
        return EvidenceAssessment('UNVERIFIED', 'Coverage probe failed or returned an invalid response.', [], False)
    if n == 0:
        return EvidenceAssessment('NO_SOURCE_COVERAGE', 'No metric-source records exist in the requested date range.', [
            'An empty source period is not a measured business value of zero.'
        ], False)
    if not isinstance(metric_result, dict) or not isinstance(metric_result.get('rows'), list):
        return EvidenceAssessment('UNVERIFIED', 'Metric execution failed or returned an invalid response.', [], False)
    rows = metric_result['rows']
    if not rows:
        return EvidenceAssessment('NO_MATCHING_GROUPS', 'Source contains records, but the compiled query returned no groups.', [
            'This does not imply that absent groups have metric value zero.',
            'Check filters, join selectivity and dimension eligibility.'
        ], False)
    if any(not isinstance(r, dict) or 'metric_value' not in r for r in rows):
        return EvidenceAssessment('UNVERIFIED', 'Returned rows do not match the expected metric schema.', [], False)
    if len(req.dimensions) == 0 and len(rows) != 1:
        return EvidenceAssessment('UNVERIFIED', 'Scalar metric returned an unexpected number of rows.', [], False)
    if any(r['metric_value'] is None for r in rows):
        return EvidenceAssessment('UNDEFINED_METRIC', 'One or more metric values are NULL, not zero.', [
            'For ratios, a zero denominator can make the metric undefined.'
        ], False)
    notes = [f'{n} metric-source rows exist during the requested period (not necessarily the joined analytical cohort).',
             'This is descriptive evidence, not a causal explanation.',
             'Source availability does not prove that all requested dimensions or groups are represented.']
    if req.dimensions:
        notes.append('Only groups with matching underlying rows are ranked; zero-activity entities are not included automatically.')
        notes.append('A ranking limited to N rows may omit other groups tied at the cutoff; alphabetical tie-breaks do not imply performance differences.')
        if len(rows) >= 2 and rows[-1]['metric_value'] == rows[-2]['metric_value']:
            notes.append('The returned groups include a tie at the displayed cutoff.')
    if len(rows) >= req.limit and req.dimensions:
        notes.append('The result reached the requested row limit; completeness and cutoff ties have not been independently checked.')
    return EvidenceAssessment('MEASURED_WITH_LIMITATIONS', 'Metric query returned measured descriptive evidence.', notes, True)
