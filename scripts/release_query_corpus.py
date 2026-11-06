"""Known SQL recorded in repository evaluation reports."""
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def saved_queries():
    def visit(value):
        if isinstance(value, list):
            for item in value:
                yield from visit(item)
        elif isinstance(value, dict):
            query = value.get("query")
            if isinstance(query, str) and query.lstrip().upper().startswith(("SELECT ", "WITH ")):
                yield query
            for item in value.values():
                yield from visit(item)
    queries = set()
    for path in (ROOT / "reports").glob("*.json"):
        queries.update(visit(json.loads(path.read_text(encoding="utf-8-sig"))))
    return sorted(queries)


def current_query(recorded):
    """Replay archived date comparisons through their current typed compilers."""
    from agent.phase4c4_drivers import compile_components
    from agent.refund_concentration import compile_plan
    period = re.search(r"WHERE order_purchase_timestamp >= DATE '([0-9-]+)' AND order_purchase_timestamp < DATE '([0-9-]+)'", recorded)
    if recorded.startswith("WITH base AS (") and period and "cx.returns" in recorded:
        return compile_plan(*period.groups(), detail=", buckets AS" in recorded)["sql"]
    dates = re.findall(r"\bDATE '(\d{4}-\d{2}-\d{2})'", recorded)
    if len(dates) == 2 and 'FROM "semantic"."order_cost_components" t0' in recorded:
        return compile_components(*dates)
    return recorded


