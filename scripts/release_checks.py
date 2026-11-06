"""Compare independently reconstructed totals to live reader and HTTP results."""
from datetime import datetime, timezone
from decimal import Decimal
import hashlib
import json
import os
from pathlib import Path
import sys
from sqlalchemy import create_engine, text
from agent.phase4c4_drivers import compile_components, COMPONENTS
from dashboard_api import month_period
from mcp_server.runtime_tools import run_readonly_sql_impl
from scripts.release_benchmark import live_api
from scripts.release_query_corpus import saved_queries, current_query
from mcp_server.runtime_tools import engine as reader
from sqlalchemy.exc import DBAPIError

ROOT = Path(__file__).resolve().parents[1]


def close(left, right, tolerance):
    return left is not None and right is not None and abs(Decimal(str(left))-Decimal(str(right))) <= Decimal(tolerance)


def run():
    sql = (ROOT / "sql/release_metric_reconciliation.sql").read_text(encoding="utf-8")
    operations = (ROOT / "sql/release_operational_reconciliation.sql").read_text(encoding="utf-8")
    from scripts.load_phase2b_v3 import DATABASE_URL, paths_for
    inputs = paths_for(ROOT)[-1]
    hashes = {}
    for name in ("olist_orders","olist_order_reviews","order_profitability","regional_capacity_overrides",
                 "inc006_effective_marketing_economics","effective_delivery_dates","cx_incident_overrides"):
        with inputs[name].open("rb") as source:
            hashes[name] = hashlib.file_digest(source, "sha256").hexdigest()
    results, gates = {}, {}
    with reader.connect() as connection:
        connection.exec_driver_sql("SELECT 1").scalar_one()
    corpus = saved_queries()
    rejected = []
    for query in corpus:
        check = run_readonly_sql_impl(current_query(query), "release corpus", "governed query", max_rows=1,timeout_ms=20000)
        if not check.ok:
            rejected.append(hashlib.sha256(query.encode()).hexdigest())
    gates["governed_query_corpus"] = bool(corpus) and not rejected
    for name, query in {
        "mcp_indirect_denied": "SELECT pg_catalog.query_to_xml('SELECT 1',true,false,'') FROM commerce.orders",
        "mcp_settings_denied": "SELECT current_setting('search_path') FROM commerce.orders",
        "mcp_hidden_cte_denied": "WITH x AS (SELECT * FROM staging.olist_orders) SELECT * FROM x",
        "mcp_unregistered_relation_denied": "SELECT * FROM semantic.order_cost_components_old",
    }.items():
        denied = run_readonly_sql_impl(query, "verify release boundary", "no rows permitted")
        gates[name] = not denied.ok and denied.data is None
    for label, probe in {
        "staging_denied":"SELECT 1 FROM staging.olist_orders LIMIT 0",
        "indirect_sql_denied":"SELECT pg_catalog.query_to_xml('SELECT 1',true,false,'')",
    }.items():
        try:
            with reader.connect() as connection:
                connection.exec_driver_sql(probe)
        except DBAPIError as exc:
            gates[label] = getattr(exc.orig, "sqlstate", None) == "42501"
        else:
            gates[label] = False
    engine = create_engine(DATABASE_URL, connect_args={"connect_timeout": 5})
    with live_api() as client, engine.begin() as conn:
        conn.exec_driver_sql("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY")
        conn.exec_driver_sql("SET LOCAL statement_timeout='30s'")
        metadata = client.get("/api/ready")
        gates["role_and_sources"] = metadata.status_code == 200
        for name in ("order_profitability","regional_capacity_overrides","inc006_effective_marketing_economics"):
            invalid = conn.exec_driver_sql(f"SELECT count(*)-count(DISTINCT order_id) FROM staging.{name}").scalar_one()
            gates["unique_"+name] = invalid == 0
        for month in ("2018-03", "2020-01"):
            response = client.get("/api/dashboard", params={"month":month})
            response.raise_for_status()
            dashboard = response.json()["metrics"]
            for side, (start, finish) in zip(("previous","current"), month_period(month)):
                row = dict(conn.execute(text(sql), {"start":start,"finish":finish}).mappings().one())
                row.update(conn.execute(text(operations), {"start":start,"finish":finish}).mappings().one())
                results[start] = dict(end_exclusive=finish, source=row)
                gates[start+"_grain"] = row["base_rows"] == row["joined_rows"] == row["finance_orders"] and row["missing_finance"] == 0
                gates[start+"_delivery_grain"] = row["orders"] == row["delivery_rows"] == row["delivery_orders"]
                checked = run_readonly_sql_impl(compile_components(start,finish),"release reconciliation","one aggregate")
                if not checked.ok:
                    gates[start+"_components"] = False
                for key in ("revenue","orders","contribution_profit","contribution_margin_pct","late_delivery_rate","average_review_score"):
                    measurement = dashboard[key]
                    results[start].setdefault("dashboard", {})[key] = measurement.get(side, {}).get("value")
                    if row["base_rows"]:
                        value = measurement.get(side,{}).get("value")
                        gates[start+"_"+key] = close(value,row[key],"0" if key=="orders" else "0.02" if key in ("revenue","contribution_profit") else "0.000001")
                    else:
                        gates[start+"_"+key] = measurement["status"] == "UNAVAILABLE"
                if not checked.ok:
                    continue
                values = checked.data["rows"][0]
                results[start]["components"] = values
                gates[start+"_counts"] = values["eligible_source_rows"] == values["distinct_orders"] == row["finance_orders"]
                for source, target in [("revenue","effective_revenue"),("contribution_profit","effective_contribution_profit"),
                                       ("effective_cogs","effective_cogs"), *[(key,key) for key in COMPONENTS]]:
                    gates[start+"_component_"+target] = (close(row[source],values[target],"0.05") if row["base_rows"]
                                                         else row[source] is None and values[target] is None)
    result = dict(checked_at=datetime.now(timezone.utc).isoformat(), database="disposable" if os.getenv("OPSLENS_DISPOSABLE_DB") else "configured",
                  readiness=metadata.json(), input_hashes=hashes, corpus=dict(count=len(corpus), failed=rejected),
                  periods=results, checks=gates, passed=all(gates.values()))
    path = ROOT / ".runtime" / ("release_checks_"+result["database"]+".json")
    path.parent.mkdir(exist_ok=True)
    path.write_text(json.dumps(result,default=str,indent=2),encoding="utf-8")
    print(path, "failed checks", [k for k,v in gates.items() if not v],flush=True)
    return result["passed"]


if __name__ == "__main__":
    sys.exit(0 if run() else 1)
