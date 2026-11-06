
from __future__ import annotations

import json
import os
import time
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Any

from dotenv import load_dotenv
from sqlalchemy import create_engine, event, text
from sqlglot import exp, parse
from sqlglot.optimizer.scope import Scope, traverse_scope
from mcp_server.policy import RELATIONS, FUNCTIONS, CAST_TYPES


ROOT = Path(__file__).resolve().parents[1]
load_dotenv(ROOT / ".env")

MCP_DATABASE_URL = os.getenv(
    "MCP_DATABASE_URL",
    "postgresql+psycopg://opslens_mcp_reader:opslens_mcp_local_dev@localhost:5432/opslens",
)

# SQL statement timeouts start after connection establishment. Bound that earlier
# wait too, so unavailable PostgreSQL cannot hold a session turn indefinitely.
CONNECT_TIMEOUT_SECONDS = int(os.getenv('MCP_CONNECT_TIMEOUT_SECONDS','5'))
if not 2 <= CONNECT_TIMEOUT_SECONDS <= 30:
    raise ValueError('MCP_CONNECT_TIMEOUT_SECONDS must be between 2 and 30')
engine = create_engine(MCP_DATABASE_URL, pool_pre_ping=True,
    connect_args={'connect_timeout':CONNECT_TIMEOUT_SECONDS},pool_timeout=10)


@event.listens_for(engine, "connect")
def verify_reader(dbapi_connection, _):
    # Metadata discovery and document retrieval use this same pool.
    with dbapi_connection.cursor() as cursor:
        cursor.execute("""
            SELECT current_user, current_setting('transaction_read_only')='on'
                AND NOT (rolsuper OR rolcreaterole OR rolcreatedb OR rolreplication OR rolbypassrls)
                AND NOT EXISTS (SELECT FROM pg_auth_members WHERE member=pg_roles.oid)
                AND NOT has_schema_privilege(current_user,'staging','USAGE')
                AND NOT has_schema_privilege(current_user,'observability','USAGE')
            FROM pg_roles WHERE rolname=current_user
        """)
        identity, restricted = cursor.fetchone()
    dbapi_connection.rollback()
    if identity != os.getenv("MCP_DB_USER", "opslens_mcp_reader") or not restricted:
        raise RuntimeError("MCP requires a dedicated read-only runtime role")

ALLOWED_SCHEMAS = {
    "commerce",
    "catalog",
    "operations",
    "finance",
    "marketing",
    "inventory",
    "cx",
    "behavior",
    "knowledge",
    "semantic",
}

FORBIDDEN_SCHEMAS = {
    "staging",
    "pg_catalog",
    "information_schema",
    "observability",
}

DEFAULT_MAX_ROWS = 200
ABSOLUTE_MAX_ROWS = 1000
DEFAULT_TIMEOUT_MS = 5000


@dataclass
class ToolResult:
    ok: bool
    tool: str
    data: Any = None
    error: str | None = None
    meta: dict[str, Any] | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def load_metric_catalog() -> dict[str, Any]:
    path = ROOT / "config" / "metric_catalog.json"
    return json.loads(path.read_text(encoding="utf-8"))


def discover_domains_impl() -> ToolResult:
    return ToolResult(
        ok=True,
        tool="discover_domains",
        data=sorted(ALLOWED_SCHEMAS),
        meta={
            "excluded": sorted(FORBIDDEN_SCHEMAS),
            "security_boundary": (
                "The MCP runtime cannot access staging or hidden eval truth."
            ),
        },
    )


def discover_schema_impl(domain: str) -> ToolResult:
    domain = domain.strip().lower()

    if domain not in ALLOWED_SCHEMAS:
        return ToolResult(
            ok=False,
            tool="discover_schema",
            error=f"Domain not allowed: {domain}",
        )

    # Metadata discovery is performed through a tightly scoped internal query.
    # This is not exposed through the generic SQL tool.
    sql = text(
        """
        SELECT
            table_schema,
            table_name,
            table_type
        FROM information_schema.tables
        WHERE table_schema = :domain
        ORDER BY table_name
        """
    )

    with engine.connect() as conn:
        rows = [
            dict(row._mapping)
            for row in conn.execute(sql, {"domain": domain})
            if f"{domain}.{row.table_name}" in RELATIONS
        ]

    return ToolResult(
        ok=True,
        tool="discover_schema",
        data=rows,
        meta={
            "domain": domain,
            "relation_count": len(rows),
        },
    )


def describe_relation_impl(schema: str, relation: str) -> ToolResult:
    schema = schema.strip().lower()
    relation = relation.strip().lower()

    if schema not in ALLOWED_SCHEMAS or f"{schema}.{relation}" not in RELATIONS:
        return ToolResult(
            ok=False,
            tool="describe_relation",
            error=f"Schema not allowed: {schema}",
        )

    sql = text(
        """
        SELECT
            ordinal_position,
            column_name,
            data_type,
            is_nullable
        FROM information_schema.columns
        WHERE table_schema = :schema
          AND table_name = :relation
        ORDER BY ordinal_position
        """
    )

    with engine.connect() as conn:
        rows = [
            dict(row._mapping)
            for row in conn.execute(
                sql,
                {"schema": schema, "relation": relation},
            )
        ]

    if not rows:
        return ToolResult(
            ok=False,
            tool="describe_relation",
            error=f"Relation not found: {schema}.{relation}",
        )

    return ToolResult(
        ok=True,
        tool="describe_relation",
        data=rows,
        meta={
            "schema": schema,
            "relation": relation,
            "column_count": len(rows),
        },
    )


def list_metrics_impl(domain: str | None = None) -> ToolResult:
    metrics = load_metric_catalog()["metrics"]

    if domain:
        normalized = domain.strip().lower()
        metrics = [
            metric
            for metric in metrics
            if metric["domain"].lower() == normalized
        ]

    return ToolResult(
        ok=True,
        tool="list_metrics",
        data=[
            {
                "metric_name": metric["metric_name"],
                "domain": metric["domain"],
                "business_definition": metric["business_definition"],
                "source_view": metric["source_view"],
            }
            for metric in metrics
        ],
        meta={"count": len(metrics)},
    )


def get_metric_definition_impl(metric_name: str) -> ToolResult:
    wanted = metric_name.strip().lower()

    for metric in load_metric_catalog()["metrics"]:
        if metric["metric_name"].lower() == wanted:
            return ToolResult(
                ok=True,
                tool="get_metric_definition",
                data=metric,
            )

    return ToolResult(
        ok=False,
        tool="get_metric_definition",
        error=f"Metric not found: {metric_name}",
    )


def _validate_select_sql(query: str) -> tuple[str, list[str]]:
    query = query.strip().rstrip(";")

    if not query:
        raise ValueError("SQL query is empty.")

    expressions = parse(query, read="postgres")

    if len(expressions) != 1:
        raise ValueError("Exactly one SQL statement is allowed.")

    root = expressions[0]

    forbidden_nodes = (
        exp.Insert,
        exp.Update,
        exp.Delete,
        exp.Create,
        exp.Drop,
        exp.Alter,
        exp.TruncateTable,
        exp.Command,
        exp.Merge,
    )

    if any(root.find(node_type) for node_type in forbidden_nodes):
        raise ValueError("Only read-only SELECT queries are allowed.")

    if not isinstance(root, exp.Query):
        raise ValueError("Only query statements are allowed.")

    # These built-ins can read SQL text, relations or whole schemas whose
    # names never appear as table nodes in the parsed outer query.
    xml_readers = {
        prefix + suffix
        for prefix in ("query", "cursor", "table", "schema", "database")
        for suffix in ("_to_xml", "_to_xmlschema", "_to_xml_and_xmlschema")
    }
    for fn in root.find_all(exp.Func):
        name = fn.name.upper() if isinstance(fn, exp.Anonymous) else fn.sql_name()
        if name.lower() in xml_readers:
            raise ValueError("Indirect XML data access is forbidden.")
        if name == "PG_INPUT_IS_VALID" and not isinstance(fn.parent, exp.Dot):
            args = fn.expressions
            if (len(args) == 2 and isinstance(args[1], exp.Literal) and args[1].is_string
                    and args[1].this == "timestamp without time zone"):
                continue
        if name not in FUNCTIONS or isinstance(fn.parent, exp.Dot):
            raise ValueError("Unregistered SQL function.")
    for dtype in root.find_all(exp.DataType):
        if getattr(dtype.this, "name", None) not in CAST_TYPES:
            raise ValueError("Unregistered SQL type.")
    if root.find(exp.Into, exp.Lock, exp.Collate, exp.Operator, exp.TableSample) or not isinstance(root, (exp.Select, exp.SetOperation)):
        raise ValueError("Unsupported SELECT operation.")

    relations: list[str] = []

    # Resolve aliases in their lexical query scope. A CTE name is not a physical
    # relation; its underlying tables still undergo the same schema checks.
    cte_references = set()
    for scope in traverse_scope(root):
        for node, source in scope.selected_sources.values():
            if isinstance(node, exp.Table) and isinstance(source, Scope):
                cte_references.add(id(node))
    for table in root.find_all(exp.Table):
        if id(table) in cte_references:
            continue
        schema = table.db
        name = table.name

        if not schema:
            raise ValueError(
                f"Unqualified relation '{name}' is not allowed. "
                "Use schema.relation explicitly."
            )

        normalized_schema = schema.lower()

        if normalized_schema in FORBIDDEN_SCHEMAS:
            raise ValueError(
                f"Access to schema '{normalized_schema}' is forbidden."
            )

        if normalized_schema not in ALLOWED_SCHEMAS:
            raise ValueError(
                f"Schema '{normalized_schema}' is not agent-accessible."
            )

        relation = f"{schema}.{name}"
        if table.catalog or relation not in RELATIONS:
            raise ValueError("Unregistered physical relation.")
        relations.append(relation)

    if not relations:
        raise ValueError(
            "Query must reference at least one approved relation."
        )

    return query, sorted(set(relations))


def _with_limit(query: str, max_rows: int) -> str:
    return (
        "SELECT * FROM ("
        + query
        + f") AS opslens_safe_query LIMIT {int(max_rows)}"
    )


def run_readonly_sql_impl(
    query: str,
    purpose: str,
    expected_grain: str,
    max_rows: int = DEFAULT_MAX_ROWS,
    timeout_ms: int = DEFAULT_TIMEOUT_MS,
) -> ToolResult:
    if not purpose or not purpose.strip():
        return ToolResult(
            ok=False,
            tool="run_readonly_sql",
            error="purpose is required",
        )

    if not expected_grain or not expected_grain.strip():
        return ToolResult(
            ok=False,
            tool="run_readonly_sql",
            error="expected_grain is required",
        )

    try:
        max_rows = min(
            max(int(max_rows), 1),
            ABSOLUTE_MAX_ROWS,
        )

        timeout_ms = min(
            max(int(timeout_ms), 100),
            30000,
        )

        validated_query, relations = _validate_select_sql(query)
        safe_query = _with_limit(validated_query, max_rows)

        started = time.perf_counter()

        with engine.begin() as conn:
            # Database role is already read-only. These are additional
            # per-transaction safeguards.
            conn.execute(text("SET LOCAL TRANSACTION READ ONLY"))
            conn.execute(text("SET LOCAL search_path = pg_catalog"))
            conn.execute(
                text(f"SET LOCAL statement_timeout = {timeout_ms}")
            )

            result = conn.execute(text(safe_query))

            columns = list(result.keys())
            rows = [
                dict(row._mapping)
                for row in result.fetchall()
            ]

        latency_ms = round(
            (time.perf_counter() - started) * 1000,
            2,
        )

        return ToolResult(
            ok=True,
            tool="run_readonly_sql",
            data={
                "columns": columns,
                "rows": rows,
            },
            meta={
                "purpose": purpose.strip(),
                "expected_grain": expected_grain.strip(),
                "relations": relations,
                "row_count": len(rows),
                "row_cap": max_rows,
                "timeout_ms": timeout_ms,
                "latency_ms": latency_ms,
            },
        )

    except Exception as exc:
        return ToolResult(
            ok=False,
            tool="run_readonly_sql",
            error=str(exc),
            meta={
                "purpose": purpose,
                "expected_grain": expected_grain,
            },
        )
