"""Conservative, metadata-checked single-relation query compiler.

Never accepts executable SQL from a model. MCP SQL guard remains mandatory.
"""
from __future__ import annotations

import re
import calendar
import math
from datetime import date
from typing import Literal
from pydantic import BaseModel, Field, model_validator

NAME = re.compile(r"^[a-z_][a-z0-9_]*$")

class Filter(BaseModel):
    column: str
    operator: Literal["eq", "neq", "gt", "gte", "lt", "lte"] = "eq"
    value: str

class QuerySpec(BaseModel):
    relation: str = Field(description="Exact schema.relation from the live approved catalog")
    aggregate: Literal["count", "sum", "avg", "min", "max"]
    measure_column: str | None = None
    group_by: list[str] = Field(default_factory=list, max_length=2)
    filters: list[Filter] = Field(default_factory=list, max_length=4)
    date_column: str | None = None
    start_date: str | None = None
    end_date_exclusive: str | None = None
    compare_previous_period: bool = False
    rationale: str = ""
    @model_validator(mode="after")
    def check_shape(self):
        if self.aggregate != "count" and not self.measure_column:
            raise ValueError("A measure column is required for non-count aggregates")
        if bool(self.start_date) != bool(self.end_date_exclusive):
            raise ValueError("Date range must have both bounds")
        if self.start_date and not self.date_column:
            raise ValueError("Date range requires a date column")
        if self.compare_previous_period and not self.start_date:
            raise ValueError("Comparison requires explicit dates")
        if self.start_date:
            a, b = date.fromisoformat(self.start_date), date.fromisoformat(self.end_date_exclusive)
            if a >= b or (b - a).days > 370:
                raise ValueError("Invalid or excessively long date window")
        return self

class QueryRejected(ValueError):
    pass

NUMERIC = ("int", "numeric", "decimal", "float", "double", "real", "money")
DATE_TYPES = ("date", "timestamp")
TEXT_TYPES = {"text", "character varying", "varchar", "character", "char", "bpchar"}
# Only well-known date/timestamp fields may be interpreted from text.
# A model cannot nominate an arbitrary text field for casting.
TEXT_DATE_COLUMNS = {
    "order_purchase_timestamp", "order_approved_at",
    "order_delivered_carrier_date", "order_delivered_customer_date",
    "order_estimated_delivery_date", "review_creation_date",
    "review_answer_timestamp", "shipping_limit_date", "event_date",
    "business_date", "order_date", "spend_date", "date",
}


def _date_expression(column: str, column_type: str) -> str:
    ident = _ident(column)
    typ = column_type.lower().strip()
    if any(token in typ for token in DATE_TYPES):
        return ident
    if typ in TEXT_TYPES and column in TEXT_DATE_COLUMNS:
        # pg_input_is_valid is available in PostgreSQL 16 (our OpsLens image).
        # CASE ensures that malformed text is not cast to timestamp.
        clean = f"NULLIF(BTRIM({ident}), '')"
        return (
            "CASE WHEN pg_input_is_valid("
            + clean
            + ", 'timestamp without time zone') "
            + f"THEN ({clean})::timestamp ELSE NULL END"
        )
    raise QueryRejected(
        f"Column {column!r} ({column_type}) is not an approved date field/type"
    )



def _ident(value: str) -> str:
    if not NAME.fullmatch(value):
        raise QueryRejected(f"Unsafe identifier: {value!r}")
    return '"' + value + '"'


def compile_query(spec: QuerySpec, columns: dict[str,str], allowed_relations: set[str], *, max_rows: int = 200) -> str:
    """Compile SQL from structured spec and live MCP column/type metadata.

    Values are conservatively escaped as SQL literals, not model-produced SQL.
    The downstream MCP service independently validates the entire SQL AST.
    """
    if spec.relation not in allowed_relations:
        raise QueryRejected("Relation not present in live approved catalog")
    parts = spec.relation.split(".")
    if len(parts) != 2:
        raise QueryRejected("Relation must be schema qualified")
    rel = ".".join(_ident(part) for part in parts)
    for col in ([spec.measure_column] if spec.measure_column else []) + spec.group_by + ([spec.date_column] if spec.date_column else []) + [f.column for f in spec.filters]:
        if col not in columns:
            raise QueryRejected(f"Column not found in live schema: {col}")
        _ident(col)
    if spec.aggregate in {"sum", "avg"} and not any(x in columns[spec.measure_column].lower() for x in NUMERIC):
        raise QueryRejected("SUM/AVG require a numeric measure")
    date_expr = _date_expression(spec.date_column, columns[spec.date_column]) if spec.date_column else None
    if len(set(spec.group_by)) != len(spec.group_by):
        raise QueryRejected("Duplicate group columns")
    agg = "COUNT(*)" if spec.aggregate == "count" else f"{spec.aggregate.upper()}({_ident(spec.measure_column)})"
    selected = [_ident(c) for c in spec.group_by] + [f"{agg} AS metric_value"]
    where = []
    if spec.start_date:
        where += [f"({date_expr}) >= DATE '{spec.start_date}'", f"({date_expr}) < DATE '{spec.end_date_exclusive}'"]
    ops = {"eq":"=", "neq":"<>", "gt":">", "gte":">=", "lt":"<", "lte":"<="}
    for f in spec.filters:
        if len(f.value) > 100:
            raise QueryRejected("Filter literal too long")
        # Basic strict literal rendering; no user input ever becomes an identifier.
        literal = "'" + f.value.replace("'", "''") + "'"
        if any(x in columns[f.column].lower() for x in NUMERIC):
            try:
                n = float(f.value)
                if not math.isfinite(n): raise ValueError("not finite")
            except ValueError: raise QueryRejected("Numeric filter requires finite numeric value")
            literal = f.value
        elif f.operator not in ("eq", "neq"):
            raise QueryRejected("Non-numeric filter only supports eq/neq")
        where.append(f"{_ident(f.column)} {ops[f.operator]} {literal}")
    group = f" GROUP BY {', '.join(str(i) for i in range(1,len(spec.group_by)+1))}" if spec.group_by else ""
    order = " ORDER BY metric_value DESC" if spec.group_by else ""
    return (f"SELECT {', '.join(selected)} FROM {rel}" + (" WHERE " + " AND ".join(where) if where else "") + group + order + f" LIMIT {min(max(max_rows,1),200)}")


def previous_window(spec: QuerySpec) -> QuerySpec:
    from datetime import timedelta
    a,b = date.fromisoformat(spec.start_date), date.fromisoformat(spec.end_date_exclusive)
    # Calendar-month comparison for explicit full calendar months, otherwise
    # compare an equally long preceding period (not mislabeled as a month).
    if a.day == 1 and b.day == 1 and (b.year * 12 + b.month) == (a.year * 12 + a.month + 1):
        y,m = (a.year-1, 12) if a.month == 1 else (a.year, a.month-1)
        previous_start = date(y,m,1)
    else:
        previous_start = a - (b-a)
    return spec.model_copy(update={"start_date":previous_start.isoformat(),"end_date_exclusive":a.isoformat(),"compare_previous_period":False})
