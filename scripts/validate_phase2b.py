from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv
from sqlalchemy import create_engine, text


ROOT = Path(__file__).resolve().parents[1]
load_dotenv(ROOT / ".env")

url = os.getenv(
    "DATABASE_URL",
    "postgresql+psycopg://opslens_admin:opslens_local_dev@localhost:5432/opslens",
)
engine = create_engine(url, pool_pre_ping=True)

checks = []

def add(name, ok, value=None):
    checks.append((name, bool(ok), value))

with engine.connect() as conn:
    # Core counts
    olist_orders = conn.execute(text("SELECT COUNT(*) FROM commerce.orders")).scalar_one()
    ga4_sessions = conn.execute(text("SELECT COUNT(*) FROM behavior.sessions")).scalar_one()
    semantic_days = conn.execute(text("SELECT COUNT(*) FROM semantic.daily_commerce")).scalar_one()
    docs = conn.execute(text("SELECT COUNT(*) FROM knowledge.documents")).scalar_one()

    add("Olist orders loaded", olist_orders == 99441, olist_orders)
    add("GA4 canonical sessions loaded", ga4_sessions == 360129, ga4_sessions)
    add("Semantic daily commerce populated", semantic_days > 0, semantic_days)
    add("Knowledge documents loaded", docs >= 4, docs)

    # No duplicate session key after canonical GA4 cleanup.
    ga4_dup = conn.execute(
        text(
            """
            SELECT COUNT(*) - COUNT(DISTINCT session_key)
            FROM behavior.sessions
            """
        )
    ).scalar_one()
    add("GA4 duplicate session_key = 0", ga4_dup == 0, ga4_dup)

    # Check effective incident layers are queryable.
    rc = conn.execute(
        text("SELECT COUNT(*) FROM staging.regional_capacity_overrides")
    ).scalar_one()
    mix = conn.execute(
        text("SELECT COUNT(*) FROM semantic.product_mix_effective")
    ).scalar_one()
    stock = conn.execute(
        text("SELECT COUNT(*) FROM semantic.stockout_effective_sales")
    ).scalar_one()
    cx = conn.execute(
        text(
            """
            SELECT COUNT(*)
            FROM cx.effective_reviews
            WHERE incident_extra_delivery_delay_days > 0
            """
        )
    ).scalar_one()

    add("INC_002 regional overrides loaded", rc > 0, rc)
    add("INC_005 effective mix loaded", mix > 0, mix)
    add("INC_007 effective stockout sales loaded", stock > 0, stock)
    add("INC_008 effective CX rows loaded", cx > 0, cx)

    # Security boundary: reader role should have no staging usage.
    staging_usage = conn.execute(
        text(
            """
            SELECT has_schema_privilege(
              'opslens_agent_reader',
              'staging',
              'USAGE'
            )
            """
        )
    ).scalar_one()
    add("Agent reader cannot use staging schema", not staging_usage, staging_usage)

    # Runtime DB must not contain eval-ground-truth-like schema/table names.
    leak_count = conn.execute(
        text(
            """
            SELECT COUNT(*)
            FROM information_schema.tables
            WHERE lower(table_schema) LIKE '%eval%'
               OR lower(table_name) LIKE '%ground_truth%'
               OR lower(table_name) LIKE 'incident_00%'
            """
        )
    ).scalar_one()
    add("No hidden ground-truth tables leaked", leak_count == 0, leak_count)

print("=" * 86)
print("OPSLENS PHASE 2B — CANONICAL DATA WORLD VALIDATION")
print("=" * 86)

passed = 0
for name, ok, value in checks:
    print(f"[{'PASS' if ok else 'FAIL'}] {name}: {value}")
    passed += int(ok)

print(f"\nChecks passed: {passed}/{len(checks)}")
verdict = "PASS" if passed == len(checks) else "REVIEW"
print("VERDICT:", verdict)

if verdict != "PASS":
    raise SystemExit(1)
