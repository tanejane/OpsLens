
from __future__ import annotations

import argparse
import json
import os
import time
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Any

from dotenv import load_dotenv
from sqlalchemy import create_engine, text
from sqlglot import exp, parse


ROOT = Path(__file__).resolve().parents[1]
load_dotenv(ROOT / ".env")

DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql+psycopg://opslens_admin:opslens_local_dev@localhost:5432/opslens",
)

engine = create_engine(DATABASE_URL, pool_pre_ping=True)

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

    def to_dict(self):
        return asdict(self)


def load_metric_catalog() -> dict:
    path = ROOT / "config" / "metric_catalog.json"
    return json.loads(path.read_text(encoding="utf-8"))


def discover_domains() -> ToolResult:
    """Return the business domains exposed to the future agent."""
    return ToolResult(
        ok=True,
        tool="discover_domains",
        data=sorted(ALLOWED_SCHEMAS),
        meta={
            "excluded": sorted(FORBIDDEN_SCHEMAS),
            "note": "staging and hidden evaluation truth are not agent-accessible",
        },
    )


def discover_schema(domain: str) -> ToolResult:
    """
    List agent-accessible relations in one approved schema.

    This is an internal metadata query. The model does not receive unrestricted
    information_schema access through run_readonly_sql().
    """
    domain = domain.strip().lower()

    if domain not in ALLOWED_SCHEMAS:
        return ToolResult(
            ok=False,
            tool="discover_schema",
            error=f"Domain not allowed: {domain}",
        )

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
            dict(r._mapping)
            for r in conn.execute(sql, {"domain": domain})
        ]

    return ToolResult(
        ok=True,
        tool="discover_schema",
        data=rows,
        meta={"domain": domain, "relation_count": len(rows)},
    )


def describe_relation(schema: str, relation: str) -> ToolResult:
    """Describe columns for one approved canonical/semantic relation."""
    schema = schema.strip().lower()
    relation = relation.strip().lower()

    if schema not in ALLOWED_SCHEMAS:
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
            dict(r._mapping)
            for r in conn.execute(
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


def list_metrics(domain: str | None = None) -> ToolResult:
    catalog = load_metric_catalog()
    metrics = catalog["metrics"]

    if domain:
        domain = domain.strip().lower()
        metrics = [
            m for m in metrics
            if m["domain"].lower() == domain
        ]

    return ToolResult(
        ok=True,
        tool="list_metrics",
        data=[
            {
                "metric_name": m["metric_name"],
                "domain": m["domain"],
                "business_definition": m["business_definition"],
                "source_view": m["source_view"],
            }
            for m in metrics
        ],
        meta={"count": len(metrics)},
    )


def get_metric_definition(metric_name: str) -> ToolResult:
    catalog = load_metric_catalog()

    for metric in catalog["metrics"]:
        if metric["metric_name"].lower() == metric_name.strip().lower():
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
    """
    Validate SQL using an AST.

    Policy:
    - exactly one statement
    - SELECT/query only
    - no DDL/DML
    - only approved schemas
    - no staging/system catalogs
    - no unqualified relation names
    """

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

    # Accept SELECTs, including WITH/CTE queries whose root is still a query.
    if not isinstance(root, exp.Query):
        raise ValueError("Only query statements are allowed.")

    relations = []

    for table in root.find_all(exp.Table):
        schema = table.db
        name = table.name

        if not schema:
            raise ValueError(
                f"Unqualified relation '{name}' is not allowed. "
                "Use schema.relation explicitly."
            )

        schema = schema.lower()

        if schema in FORBIDDEN_SCHEMAS:
            raise ValueError(
                f"Access to schema '{schema}' is forbidden."
            )

        if schema not in ALLOWED_SCHEMAS:
            raise ValueError(
                f"Schema '{schema}' is not agent-accessible."
            )

        relations.append(f"{schema}.{name}")

    if not relations:
        raise ValueError("Query must reference at least one approved relation.")

    return query, sorted(set(relations))


def _with_limit(query: str, max_rows: int) -> str:
    """
    Wrap the validated query so callers cannot bypass the row cap even if their
    SQL contains its own LIMIT.
    """
    return (
        "SELECT * FROM ("
        + query
        + f") AS opslens_safe_query LIMIT {int(max_rows)}"
    )


def run_readonly_sql(
    query: str,
    purpose: str,
    expected_grain: str,
    max_rows: int = DEFAULT_MAX_ROWS,
    timeout_ms: int = DEFAULT_TIMEOUT_MS,
) -> ToolResult:
    """
    Execute a validated business investigation query.

    `purpose` and `expected_grain` are mandatory because later traces/evals must
    judge whether the tool call was necessary and whether the returned grain
    matched the investigation plan.
    """

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
        max_rows = int(max_rows)
        timeout_ms = int(timeout_ms)

        if max_rows < 1:
            raise ValueError("max_rows must be >= 1")

        max_rows = min(max_rows, ABSOLUTE_MAX_ROWS)
        timeout_ms = max(100, min(timeout_ms, 30000))

        validated_query, relations = _validate_select_sql(query)
        safe_query = _with_limit(validated_query, max_rows)

        started = time.perf_counter()

        with engine.begin() as conn:
            conn.execute(
                text(f"SET LOCAL statement_timeout = {timeout_ms}")
            )
            result = conn.execute(text(safe_query))
            columns = list(result.keys())
            rows = [dict(r._mapping) for r in result.fetchall()]

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


def self_test() -> int:
    print("=" * 86)
    print("OPSLENS PHASE 2C — SEMANTIC + SAFE SQL TOOL CONTRACT VALIDATION")
    print("=" * 86)

    checks: list[tuple[str, bool, Any]] = []

    def add(name: str, passed: bool, value: Any):
        checks.append((name, bool(passed), value))

    domains = discover_domains()
    add(
        "Domains discoverable",
        domains.ok and "semantic" in domains.data,
        domains.data,
    )

    finance_schema = discover_schema("finance")
    add(
        "Finance schema discoverable",
        finance_schema.ok and len(finance_schema.data) > 0,
        finance_schema.meta,
    )

    relation = describe_relation(
        "semantic",
        "daily_commerce",
    )
    add(
        "Semantic relation describable",
        relation.ok and relation.meta["column_count"] >= 5,
        relation.meta,
    )

    metric_list = list_metrics()
    add(
        "Metric catalog populated",
        metric_list.ok and metric_list.meta["count"] >= 8,
        metric_list.meta,
    )

    cm = get_metric_definition("contribution_margin")
    add(
        "Contribution margin definition available",
        cm.ok
        and "ratio of sums" in " ".join(cm.data["known_limitations"]).lower(),
        cm.data["business_definition"] if cm.ok else cm.error,
    )

    good_query = run_readonly_sql(
        query="""
            SELECT
                business_date,
                revenue,
                contribution_profit,
                contribution_margin
            FROM semantic.daily_commerce
            ORDER BY business_date
        """,
        purpose="Inspect daily commerce economics",
        expected_grain="one row per business date",
        max_rows=25,
    )
    add(
        "Approved semantic SELECT executes",
        good_query.ok and good_query.meta["row_count"] <= 25,
        good_query.meta if good_query.ok else good_query.error,
    )

    staging_query = run_readonly_sql(
        query="SELECT * FROM staging.olist_orders",
        purpose="Attempt forbidden staging access",
        expected_grain="order",
        max_rows=5,
    )
    add(
        "Staging access blocked",
        not staging_query.ok,
        staging_query.error,
    )

    delete_query = run_readonly_sql(
        query="DELETE FROM semantic.daily_commerce",
        purpose="Attempt write",
        expected_grain="n/a",
        max_rows=5,
    )
    add(
        "Write statement blocked",
        not delete_query.ok,
        delete_query.error,
    )

    unqualified_query = run_readonly_sql(
        query="SELECT * FROM daily_commerce",
        purpose="Attempt ambiguous access",
        expected_grain="day",
        max_rows=5,
    )
    add(
        "Unqualified relation blocked",
        not unqualified_query.ok,
        unqualified_query.error,
    )

    system_query = run_readonly_sql(
        query="SELECT * FROM information_schema.tables",
        purpose="Attempt system catalog access",
        expected_grain="relation",
        max_rows=5,
    )
    add(
        "System catalog blocked from generic SQL tool",
        not system_query.ok,
        system_query.error,
    )

    passed_count = 0

    for name, passed, value in checks:
        print(
            f"[{'PASS' if passed else 'FAIL'}] "
            f"{name}: {value}"
        )
        passed_count += int(passed)

    print(
        f"\nChecks passed: "
        f"{passed_count}/{len(checks)}"
    )

    verdict = (
        "PASS"
        if passed_count == len(checks)
        else "REVIEW"
    )

    print("VERDICT:", verdict)

    return 0 if verdict == "PASS" else 1


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--self-test",
        action="store_true",
        help="Run Phase 2C validation checks.",
    )
    parser.add_argument(
        "--demo",
        action="store_true",
        help="Print example tool outputs.",
    )
    args = parser.parse_args()

    if args.self_test:
        raise SystemExit(self_test())

    if args.demo:
        for result in [
            discover_domains(),
            list_metrics(),
            get_metric_definition("contribution_margin"),
        ]:
            print(
                json.dumps(
                    result.to_dict(),
                    indent=2,
                    default=str,
                )
            )
        return

    parser.print_help()


if __name__ == "__main__":
    main()
