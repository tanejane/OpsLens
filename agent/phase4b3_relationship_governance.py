"""Phase 4B.3: approved analytical relationship contracts; no model-authored SQL."""
from __future__ import annotations
from dataclasses import dataclass
from datetime import date
from typing import Literal
from pydantic import BaseModel, Field, model_validator
from agent.phase4b1_semantic_query import QueryRejected, _ident, _date_expression

@dataclass(frozen=True)
class RelationContract:
    metric: str
    dimension: str
    sources: tuple[str, ...]
    grain: str
    meaning: str
    required: dict[str, tuple[str, ...]]
    join_keys: tuple[str, str] | None = None

CONTRACTS = {
 ('unique_orders', 'seller_id'): RelationContract(
    'unique_orders','seller_id',('commerce.orders','commerce.order_items'),
    'one seller per distinct order',
    'Number of unique placed orders per seller; an order can be counted for more than one seller',
    {'commerce.orders':('order_id','order_purchase_timestamp'), 'commerce.order_items':('order_id','seller_id')},
    ('order_id','order_id')),
 ('gross_margin_pct', 'category'): RelationContract(
    'gross_margin_pct','category',('semantic.product_mix_effective',),
    'effective item/category economics',
    'Effective product-mix gross margin; incident-oriented source, NOT canonical marketplace-wide gross margin',
    {'semantic.product_mix_effective':('order_id','category','effective_revenue','effective_cogs')},
 ),
}

class RelationshipRequest(BaseModel):
    metric: Literal['unique_orders','gross_margin_pct']
    dimension: Literal['seller_id','category']
    start_date: str
    end_date_exclusive: str
    order: Literal['asc','desc'] = 'desc'
    limit: int = Field(default=10,ge=1,le=100)
    @model_validator(mode='after')
    def check_dates(self):
        a,b=date.fromisoformat(self.start_date),date.fromisoformat(self.end_date_exclusive)
        if a>=b or (b-a).days>370: raise ValueError('Date range must be valid and <= 370 days')
        return self

def compile_relationship(req: RelationshipRequest, live: dict[str,dict[str,str]], approved: set[str]) -> tuple[str,RelationContract]:
    contract=CONTRACTS.get((req.metric, req.dimension))
    if not contract: raise QueryRejected('No approved metric-dimension relationship; refuse approximation')
    for rel,cols in contract.required.items():
        if rel not in approved: raise QueryRejected(f'Relation not in live approved catalog: {rel}')
        missing=set(cols)-set(live.get(rel,{}))
        if missing: raise QueryRejected(f'Missing live relation columns: {rel} {sorted(missing)}')
    lo,hi=req.start_date,req.end_date_exclusive
    if contract.metric=='unique_orders':
        dt=_date_expression('order_purchase_timestamp',live['commerce.orders']['order_purchase_timestamp']).replace('\"order_purchase_timestamp\"','o.\"order_purchase_timestamp\"')
        sql=(f'SELECT i."seller_id" AS dimension_value, COUNT(DISTINCT o."order_id") AS metric_value '
            f'FROM "commerce"."orders" AS o '
            f'INNER JOIN "commerce"."order_items" AS i ON o."order_id" = i."order_id" '
            f"WHERE ({dt}) >= DATE '{lo}' AND ({dt}) < DATE '{hi}' "
            f'GROUP BY i."seller_id" ORDER BY metric_value {req.order.upper()} NULLS LAST, dimension_value ASC LIMIT {req.limit}')
    else:
        # Dates must be applied via commerce.orders; item mix view has no timestamp.
        # This is an approved many-to-one join. Item measures are aggregated only from m.
        if 'commerce.orders' not in approved: raise QueryRejected('Approved order relation missing for category date scoping')
        cols=live.get('commerce.orders',{})
        if not {'order_id','order_purchase_timestamp'}.issubset(cols): raise QueryRejected('Order join/date columns not present in live metadata')
        dt=_date_expression('order_purchase_timestamp',cols['order_purchase_timestamp']).replace('\"order_purchase_timestamp\"','o.\"order_purchase_timestamp\"')
        sql=(f'SELECT m."category" AS dimension_value, '
             f'100.0 * (SUM(m."effective_revenue") - SUM(m."effective_cogs")) '
             f'/ NULLIF(SUM(m."effective_revenue"),0) AS metric_value '
             f'FROM "semantic"."product_mix_effective" AS m '
             f'INNER JOIN "commerce"."orders" AS o ON m."order_id" = o."order_id" '
             f"WHERE ({dt}) >= DATE '{lo}' AND ({dt}) < DATE '{hi}' "
             f'GROUP BY m."category" ORDER BY metric_value {req.order.upper()} NULLS LAST, dimension_value ASC LIMIT {req.limit}')
    return sql, contract
