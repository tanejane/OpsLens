"""Phase 4B.2: fail-closed business metrics, validated against live MCP columns.

This is intentionally NOT a generic join planner. Never trust a model's formulas.
"""
from __future__ import annotations
from dataclasses import dataclass
from datetime import date
from typing import Literal
from pydantic import BaseModel, Field, model_validator
from agent.phase4b1_semantic_query import _date_expression, _ident, QueryRejected

@dataclass(frozen=True)
class Metric:
    source: str
    expression: str
    required_columns: tuple[str, ...]
    date_column: str
    dimensions: tuple[str, ...]
    meaning: str
    grain: str

# Expressions below are application-owned, not accepted from the model.
# Semantic daily_commerce is already aggregated by day, so orders MUST be
# SUM(orders) there, not COUNT(DISTINCT order_id).
METRICS = {
    'orders': Metric('commerce.orders','COUNT(DISTINCT "order_id")',('order_id','order_purchase_timestamp'),'order_purchase_timestamp',('order_status',),'Distinct placed Olist orders','order'),
    'revenue': Metric('semantic.daily_commerce','SUM("revenue")',('revenue','business_date'),'business_date',(), 'Effective commerce revenue','daily commerce'),
    'gross_profit': Metric('semantic.daily_commerce','SUM("revenue") - SUM("cogs")',('revenue','cogs','business_date'),'business_date',(), 'Effective revenue less effective COGS','daily commerce'),
    'gross_margin_pct': Metric('semantic.daily_commerce','100.0 * (SUM("revenue") - SUM("cogs")) / NULLIF(SUM("revenue"),0)',('revenue','cogs','business_date'),'business_date',(), 'Ratio of aggregated gross profit to aggregated revenue, percent','daily commerce'),
    'contribution_profit': Metric('semantic.daily_commerce','SUM("contribution_profit")',('contribution_profit','business_date'),'business_date',(), 'Effective contribution profit','daily commerce'),
    'contribution_margin_pct': Metric('semantic.daily_commerce','100.0 * SUM("contribution_profit") / NULLIF(SUM("revenue"),0)',('contribution_profit','revenue','business_date'),'business_date',(), 'Revenue-weighted contribution margin in percent','daily commerce'),
    'review_score': Metric('cx.effective_reviews','AVG("effective_review_score")',('effective_review_score','review_creation_date'),'review_creation_date',(), 'Average effective review score by review creation date','review'),
    'purchase_session_rate_pct': Metric('semantic.ga4_funnel_daily','100.0 * SUM("purchase_sessions") / NULLIF(SUM("sessions"),0)',('purchase_sessions','sessions','session_date'),'session_date',(), 'Share of sessions with a purchase (percent)','daily GA4 sessions'),
    'checkout_abandon_rate_pct': Metric('semantic.ga4_funnel_daily','100.0 * SUM("checkout_abandon_sessions") / NULLIF(SUM("checkout_sessions"),0)',('checkout_abandon_sessions','checkout_sessions','session_date'),'session_date',(), 'Checkout-abandon sessions / checkout sessions (percent)','daily GA4 sessions'),
}
# Checkout abandon numerator is NOT in the audited view! The metric is intentionally
# not executable until a validated view/column supplies that numerator.

class MetricRequest(BaseModel):
    metric: str
    dimensions: list[str] = Field(default_factory=list, max_length=2)
    start_date: str | None = None
    end_date_exclusive: str | None = None
    order: Literal['asc','desc'] = 'desc'
    limit: int = Field(default=10, ge=1, le=100)
    @model_validator(mode='after')
    def validate_dates(self):
        if bool(self.start_date) != bool(self.end_date_exclusive):
            raise ValueError('Both date bounds are required')
        if self.start_date:
            a,b = date.fromisoformat(self.start_date),date.fromisoformat(self.end_date_exclusive)
            if a >= b or (b-a).days > 370: raise ValueError('Invalid date window')
        return self

def compile_metric(request: MetricRequest, live_columns: dict[str,str], approved_relations: set[str]) -> str:
    if request.metric not in METRICS: raise QueryRejected('Unregistered metric; definition required')
    metric=METRICS[request.metric]
    if metric.source not in approved_relations: raise QueryRejected('Metric source not approved by live MCP')
    missing=[c for c in metric.required_columns if c not in live_columns]
    if missing: raise QueryRejected(f'Metric not executable: source {metric.source} missing {missing}')
    if len(set(request.dimensions))!=len(request.dimensions): raise QueryRejected('Duplicate dimensions')
    for d in request.dimensions:
        if d not in metric.dimensions: raise QueryRejected(f'Dimension {d!r} requires a separately approved relationship/grain; cannot use {metric.source}')
        if d not in live_columns: raise QueryRejected(f'Dimension {d!r} not found in live source')
    schema,table=metric.source.split('.')
    dim_sql=[_ident(d) for d in request.dimensions]
    where=''
    if request.start_date:
        date_expr=_date_expression(metric.date_column,live_columns[metric.date_column])
        where=f" WHERE ({date_expr}) >= DATE '{request.start_date}' AND ({date_expr}) < DATE '{request.end_date_exclusive}'"
    select=', '.join(dim_sql+[f'{metric.expression} AS metric_value'])
    group=f' GROUP BY {", ".join(str(i) for i in range(1,len(dim_sql)+1))}' if dim_sql else ''
    sort=f' ORDER BY metric_value {request.order.upper()} NULLS LAST' if dim_sql else ''
    return f'SELECT {select} FROM {_ident(schema)}.{_ident(table)}{where}{group}{sort} LIMIT {request.limit}'
