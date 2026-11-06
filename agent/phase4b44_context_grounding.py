"""Phase 4B.4.4: constrained natural-language -> semantic graph requests.

The LLM proposes intent IDs, not SQL. State is session-local, never persisted.
Only graph compiler can authorize execution. No keyword-based question recipes.
"""
from __future__ import annotations
from dataclasses import dataclass
from datetime import date
from typing import Literal
from pydantic import BaseModel, ConfigDict, Field
from agent.phase4b43_graph_planner import AnalysisRequest, PlanningRejected

class Interpretation(BaseModel):
    model_config = ConfigDict(extra='forbid')
    intent: Literal['descriptive','ranking','comparison','investigation','clarification']
    metric_id: str | None = None
    dimensions: list[str] = Field(default_factory=list)
    start_date: str | None = None
    end_date_exclusive: str | None = None
    order: Literal['asc','desc'] | None = None
    limit: int | None = None
    # Explicitly states which fields refer to previous validated conversational context.
    inherit: list[Literal['metric','dimensions','period','order','limit']] = Field(default_factory=list)
    ambiguity: str | None = None
    rationale: str = ''

@dataclass(frozen=True)
class GroundedTurn:
    interpretation: Interpretation
    request: AnalysisRequest | None
    status: Literal['READY','NEEDS_CLARIFICATION','INVESTIGATION_NOT_EXECUTED','UNSUPPORTED']
    message: str

def public_catalog(semantic_map) -> dict:
    """Bounded list of business terms; never exposes evaluator incident truth."""
    return {
      'metrics': [{'id':k,'definition':v.get('definition',''), 'dimensions':v.get('allowed_dimensions',[]),
                   'source':v.get('source')} for k,v in semantic_map.metrics.items()
                  if semantic_map.sources[v['source']].get('scope')!='incident_specific'],
      'dimensions':[{'id':k,'source':v['source']} for k,v in semantic_map.dimensions.items()
                    if semantic_map.sources[v['source']].get('scope')!='incident_specific'],
      'rules': ['Olist orders and GA4 sessions are separate environments.',
                'A metric must exist in the catalog; never approximate it with another metric.',
                'Profit margin and profit amount are distinct; order counts and item counts are distinct.',
                'No implicit date or population. Relative dates require an explicit reference date.',
                'Why/causal questions are investigation requests, never causal answers from a single metric.']}

def _date_pair(lo,hi):
    if (lo is None) != (hi is None):raise ValueError('Both date boundaries required')
    if lo is not None:
        try: a,b=date.fromisoformat(lo),date.fromisoformat(hi)
        except (ValueError,TypeError):raise ValueError('Invalid ISO date') from None
        if a>=b:raise ValueError('Date interval must be positive')
    return lo,hi

def ground(meaning:Interpretation, semantic_map, previous:AnalysisRequest|None=None) -> GroundedTurn:
    catalog=public_catalog(semantic_map)
    allowed_metrics={m['id'] for m in catalog['metrics']}
    allowed_dims={d['id'] for d in catalog['dimensions']}
    if len(set(meaning.inherit))!=len(meaning.inherit):
        return GroundedTurn(meaning,None,'UNSUPPORTED','Duplicate inherited fields')
    if meaning.inherit and previous is None:
        return GroundedTurn(meaning,None,'NEEDS_CLARIFICATION','There is no preceding validated analytical request to inherit.')
    if meaning.ambiguity or meaning.intent=='clarification':
        return GroundedTurn(meaning,None,'NEEDS_CLARIFICATION',meaning.ambiguity or 'Which business metric and population do you mean?')
    if meaning.intent=='investigation':
        return GroundedTurn(meaning,None,'INVESTIGATION_NOT_EXECUTED',
          'An investigation requires verifying the outcome and testing hypotheses; no cause has been established.')
    def inherited(key,explicit,prior):
        if key in meaning.inherit:
            if explicit is not None:return (None,f'Conflicting explicit and inherited {key}')
            return prior,None
        return explicit,None
    metric,err=inherited('metric',meaning.metric_id,previous.metric if previous else None)
    if err:return GroundedTurn(meaning,None,'UNSUPPORTED',err)
    dims,err=inherited('dimensions',meaning.dimensions or None,previous.dimensions if previous else None)
    if err:return GroundedTurn(meaning,None,'UNSUPPORTED',err)
    dims=tuple(dims or ())
    if not metric or metric not in allowed_metrics:
        return GroundedTurn(meaning,None,'NEEDS_CLARIFICATION','Select a registered metric; no inferred substitute is permitted.')
    if any(d not in allowed_dims for d in dims):
        return GroundedTurn(meaning,None,'UNSUPPORTED','An unregistered dimension was requested.')
    if 'period' in meaning.inherit:
        if meaning.start_date or meaning.end_date_exclusive:
            return GroundedTurn(meaning,None,'UNSUPPORTED','Conflicting explicit and inherited period')
        lo,hi=previous.start_date,previous.end_date_exclusive
    else: lo,hi=meaning.start_date,meaning.end_date_exclusive
    try: _date_pair(lo,hi)
    except ValueError as exc: return GroundedTurn(meaning,None,'NEEDS_CLARIFICATION',str(exc))
    if not lo:
        return GroundedTurn(meaning,None,'NEEDS_CLARIFICATION','Specify the analysis date range.')
    order,err=inherited('order',meaning.order,previous.order if previous else None)
    if err:return GroundedTurn(meaning,None,'UNSUPPORTED',err)
    limit,err=inherited('limit',meaning.limit,previous.limit if previous else None)
    if err:return GroundedTurn(meaning,None,'UNSUPPORTED',err)
    order=order or 'desc';limit=10 if limit is None else limit
    if isinstance(limit,bool) or not isinstance(limit,int) or not 1<=limit<=100:
        return GroundedTurn(meaning,None,'UNSUPPORTED','Limit must be 1..100')
    request=AnalysisRequest(metric, dims,lo,hi,order,limit)
    definition=semantic_map.metrics[metric]
    if any(d not in definition['allowed_dimensions'] for d in dims):
        return GroundedTurn(meaning,None,'UNSUPPORTED','Metric and dimension are not compatible in the semantic map.')
    if meaning.intent=='comparison':
        return GroundedTurn(meaning,None,'UNSUPPORTED','Multi-period comparison is not yet supported by this graph compiler.')
    return GroundedTurn(meaning,request,'READY','Grounded in registered semantic IDs; SQL still requires graph compilation.')
