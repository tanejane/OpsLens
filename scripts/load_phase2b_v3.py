
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

import pandas as pd
from dotenv import load_dotenv
from sqlalchemy import create_engine, text


# =============================================================================
# OpsLens Phase 2B
# Deterministic ingestion + canonical/effective PostgreSQL views
#
# Security rule:
#   data/eval_ground_truth is NEVER loaded into the runtime database.
#
# Usage:
#   Full load + views:
#       python scripts/load_phase2b_v3.py --project-root .
#
#   Views only (use this now because staging is already loaded):
#       python scripts/load_phase2b_v3.py --project-root . --views-only
# =============================================================================


ROOT = Path(__file__).resolve().parents[1]
load_dotenv(ROOT / ".env")

DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql+psycopg://opslens_admin:opslens_local_dev@localhost:5432/opslens",
)

engine = create_engine(DATABASE_URL, pool_pre_ping=True)


def paths_for(root: Path):
    raw_olist = root / "data" / "raw" / "olist"
    synth = root / "data" / "synthetic"
    processed = root / "data" / "processed"
    docs = root / "data" / "documents"

    csv_sources = {
        # ---------------------------------------------------------------------
        # Real Olist data
        # ---------------------------------------------------------------------
        "olist_customers": raw_olist / "olist_customers_dataset.csv",
        "olist_orders": raw_olist / "olist_orders_dataset.csv",
        "olist_order_items": raw_olist / "olist_order_items_dataset.csv",
        "olist_order_payments": raw_olist / "olist_order_payments_dataset.csv",
        "olist_order_reviews": raw_olist / "olist_order_reviews_dataset.csv",
        "olist_products": raw_olist / "olist_products_dataset.csv",
        "olist_sellers": raw_olist / "olist_sellers_dataset.csv",
        "product_category_translation": raw_olist / "product_category_name_translation.csv",

        # ---------------------------------------------------------------------
        # Processed runtime data
        # ---------------------------------------------------------------------
        "order_profitability": processed / "order_profitability.csv",
        "daily_pnl": processed / "daily_pnl.csv",
        "ga4_sessions": processed / "ga4_sessions_clean.csv",

        # ---------------------------------------------------------------------
        # Controlled synthetic / effective business layers
        # ---------------------------------------------------------------------
        "product_cost_history": synth / "product_cost_history.csv",
        "marketing_campaigns": synth / "marketing_campaigns.csv",
        "marketing_spend_daily": synth / "marketing_spend_daily.csv",
        "order_campaign_attribution": synth / "order_campaign_attribution.csv",
        "returns": synth / "returns.csv",
        "inventory_weekly": synth / "inventory_weekly.csv",

        # Incident-effective layers
        "regional_capacity_overrides": synth / "regional_capacity_overrides.csv",
        "product_quality_events": synth / "product_quality_events.csv",
        "effective_delivery_dates": synth / "effective_delivery_dates.csv",
        "product_mix_overrides": synth / "product_mix_overrides.csv",
        "inc005_effective_mix_economics": synth / "inc005_effective_mix_economics.csv",
        "inc006_campaign": synth / "inc006_campaign.csv",
        "inc006_order_marketing_economics": synth / "inc006_order_marketing_economics.csv",
        "inc006_effective_marketing_economics": synth / "inc006_effective_marketing_economics.csv",
        "stockout_events": synth / "stockout_events.csv",
        "inc007_effective_sales": synth / "inc007_effective_sales.csv",
        "cx_incident_overrides": synth / "cx_incident_overrides.csv",
        "inc012_misleading_correlation": synth / "inc012_misleading_correlation.csv",
    }

    return raw_olist, synth, processed, docs, csv_sources


def normalize_columns(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df.columns = [
        str(c).strip().lower().replace(" ", "_").replace("-", "_")
        for c in df.columns
    ]
    return df


def load_csv(table_name: str, path: Path, *, method=None) -> tuple[int, int]:
    if not path.exists():
        print(f"[SKIP] {table_name}: file not found -> {path}")
        return 0, 0

    df = pd.read_csv(path, low_memory=False)
    df = normalize_columns(df)

    # Conservative executemany batching.
    # Avoid method="multi" because wide tables can exceed bind-parameter limits.
    df.to_sql(
        table_name,
        engine,
        schema="staging",
        if_exists="replace",
        index=False,
        chunksize=2_000,
        method=method,
    )

    print(
        f"[LOAD] staging.{table_name}: "
        f"{len(df):,} rows × {len(df.columns)} cols"
    )
    return len(df), len(df.columns)


def load_documents(root: Path, docs: Path) -> int:
    docs.mkdir(parents=True, exist_ok=True)

    rows = []

    for path in sorted(docs.rglob("*")):
        if not path.is_file():
            continue
        if path.suffix.lower() not in {".md", ".txt"}:
            continue

        content = path.read_text(
            encoding="utf-8",
            errors="replace",
        )

        rows.append(
            {
                "document_id": path.stem,
                "filename": path.name,
                "relative_path": str(
                    path.relative_to(root)
                ).replace("\\", "/"),
                "content": content,
                "source_type": "internal_document_fixture",
                "trust_level": (
                    "untrusted_external"
                    if (
                        "prompt_injection" in path.name.lower()
                        or "vendor" in path.name.lower()
                    )
                    else "internal"
                ),
            }
        )

    if not rows:
        print("[SKIP] staging.documents: no .md/.txt documents found")
        return 0

    df = pd.DataFrame(rows)

    df.to_sql(
        "documents",
        engine,
        schema="staging",
        if_exists="replace",
        index=False,
        chunksize=500,
        method=None,
    )

    print(f"[LOAD] staging.documents: {len(df):,} rows")
    return len(df)


def assert_runtime_manifest_safe(csv_sources: dict[str, Path]):
    manifest_text = "\n".join(
        str(path).lower()
        for path in csv_sources.values()
    )

    if "eval_ground_truth" in manifest_text:
        raise RuntimeError(
            "SECURITY ERROR: eval_ground_truth must never be ingested."
        )


def staging_table_exists(conn, table_name: str) -> bool:
    return bool(
        conn.execute(
            text(
                """
                SELECT EXISTS (
                    SELECT 1
                    FROM information_schema.tables
                    WHERE table_schema = 'staging'
                      AND table_name = :table_name
                )
                """
            ),
            {"table_name": table_name},
        ).scalar_one()
    )


def require_staging_tables():
    required = {
        "olist_customers",
        "olist_orders",
        "olist_order_items",
        "olist_order_payments",
        "olist_order_reviews",
        "olist_products",
        "olist_sellers",
        "product_category_translation",
        "order_profitability",
        "daily_pnl",
        "ga4_sessions",
        "marketing_campaigns",
        "marketing_spend_daily",
        "order_campaign_attribution",
        "returns",
        "inventory_weekly",
        "regional_capacity_overrides",
        "effective_delivery_dates",
        "inc005_effective_mix_economics",
        "inc006_campaign",
        "inc006_effective_marketing_economics",
        "stockout_events",
        "inc007_effective_sales",
        "cx_incident_overrides",
        "inc012_misleading_correlation",
        "documents",
    }

    with engine.connect() as conn:
        missing = [
            name
            for name in sorted(required)
            if not staging_table_exists(conn, name)
        ]

    if missing:
        raise RuntimeError(
            "Missing required staging tables:\n- "
            + "\n- ".join(missing)
            + "\n\nRun without --views-only first."
        )


def execute_sql(conn, sql: str):
    conn.execute(text(sql))


def create_canonical_views():
    """
    Create the runtime domain views and agent-facing semantic layer.

    We execute statements individually so any future error points to a specific
    business view rather than one giant SQL migration.
    """

    print("\n" + "=" * 82)
    print("CREATING CANONICAL / EFFECTIVE VIEWS")
    print("=" * 82)

    statements = [
        # =====================================================================
        # COMMERCE
        # =====================================================================
        (
            "commerce.customers",
            """
            DROP VIEW IF EXISTS commerce.customers CASCADE;
            CREATE VIEW commerce.customers AS
            SELECT *
            FROM staging.olist_customers;
            """,
        ),
        (
            "commerce.orders",
            """
            DROP VIEW IF EXISTS commerce.orders CASCADE;
            CREATE VIEW commerce.orders AS
            SELECT *
            FROM staging.olist_orders;
            """,
        ),
        (
            "commerce.order_items",
            """
            DROP VIEW IF EXISTS commerce.order_items CASCADE;
            CREATE VIEW commerce.order_items AS
            SELECT *
            FROM staging.olist_order_items;
            """,
        ),
        (
            "commerce.payments",
            """
            DROP VIEW IF EXISTS commerce.payments CASCADE;
            CREATE VIEW commerce.payments AS
            SELECT *
            FROM staging.olist_order_payments;
            """,
        ),

        # =====================================================================
        # CATALOG
        # =====================================================================
        (
            "catalog.products",
            """
            DROP VIEW IF EXISTS catalog.products CASCADE;
            CREATE VIEW catalog.products AS
            SELECT
                p.*,
                COALESCE(
                    t.product_category_name_english,
                    p.product_category_name,
                    'unknown'
                ) AS category
            FROM staging.olist_products p
            LEFT JOIN staging.product_category_translation t
              ON p.product_category_name = t.product_category_name;
            """,
        ),

        # =====================================================================
        # OPERATIONS
        # =====================================================================
        (
            "operations.sellers",
            """
            DROP VIEW IF EXISTS operations.sellers CASCADE;
            CREATE VIEW operations.sellers AS
            SELECT *
            FROM staging.olist_sellers;
            """,
        ),
        (
            "operations.delivery_effective",
            """
            DROP VIEW IF EXISTS operations.delivery_effective CASCADE;
            CREATE VIEW operations.delivery_effective AS
            SELECT
                o.order_id,
                o.order_purchase_timestamp,
                o.order_delivered_customer_date
                    AS baseline_delivered_customer_date,
                o.order_estimated_delivery_date,

                COALESCE(
                    NULLIF(
                        ed.effective_delivered_customer_date,
                        ''
                    )::timestamp,
                    NULLIF(
                        o.order_delivered_customer_date,
                        ''
                    )::timestamp
                ) AS effective_delivered_customer_date,

                COALESCE(
                    ed.extra_delay_days::double precision,
                    0
                ) AS inc004_extra_delay_days,

                COALESCE(
                    rc.extra_delivery_delay_days::double precision,
                    0
                ) AS inc002_extra_delay_days,

                COALESCE(
                    cx.extra_delivery_delay_days::double precision,
                    0
                ) AS inc008_extra_delay_days,

                COALESCE(
                    rc.capacity_impact,
                    'none'
                ) AS regional_capacity_impact,

                (
                    COALESCE(
                        NULLIF(
                            ed.effective_delivered_customer_date,
                            ''
                        )::timestamp,
                        NULLIF(
                            o.order_delivered_customer_date,
                            ''
                        )::timestamp
                    )
                    + make_interval(
                        days => COALESCE(
                            rc.extra_delivery_delay_days::numeric,
                            0
                        )::int
                    )
                    + make_interval(
                        days => COALESCE(
                            cx.extra_delivery_delay_days::numeric,
                            0
                        )::int
                    )
                ) AS final_effective_delivered_customer_date

            FROM staging.olist_orders o
            LEFT JOIN staging.effective_delivery_dates ed
              USING (order_id)
            LEFT JOIN staging.regional_capacity_overrides rc
              USING (order_id)
            LEFT JOIN staging.cx_incident_overrides cx
              USING (order_id);
            """,
        ),

        # =====================================================================
        # FINANCE
        # =====================================================================
        (
            "finance.order_profitability_base",
            """
            DROP VIEW IF EXISTS finance.order_profitability_base CASCADE;
            CREATE VIEW finance.order_profitability_base AS
            SELECT *
            FROM staging.order_profitability;
            """,
        ),
        (
            "finance.order_profitability_effective",
            """
            DROP VIEW IF EXISTS finance.order_profitability_effective CASCADE;
            CREATE VIEW finance.order_profitability_effective AS
            SELECT
                p.*,

                COALESCE(
                    rc.recognized_revenue_multiplier::double precision,
                    1.0
                ) AS regional_revenue_multiplier,

                COALESCE(
                    m6.incremental_revenue::double precision,
                    0.0
                ) AS inc006_incremental_revenue,

                COALESCE(
                    m6.incremental_cogs::double precision,
                    0.0
                ) AS inc006_incremental_cogs,

                COALESCE(
                    m6.inc006_allocated_marketing_cost::double precision,
                    0.0
                ) AS inc006_marketing_cost,

                COALESCE(
                    m6.inc006_campaign_incentive_cost::double precision,
                    0.0
                ) AS inc006_incentive_cost,

                (
                    COALESCE(
                        p.revenue::double precision,
                        0.0
                    )
                    * COALESCE(
                        rc.recognized_revenue_multiplier::double precision,
                        1.0
                    )
                    + COALESCE(
                        m6.incremental_revenue::double precision,
                        0.0
                    )
                ) AS effective_revenue,

                (
                    COALESCE(
                        p.cogs::double precision,
                        0.0
                    )
                    + COALESCE(
                        m6.incremental_cogs::double precision,
                        0.0
                    )
                ) AS effective_cogs,

                (
                    COALESCE(
                        p.contribution_profit::double precision,
                        0.0
                    )
                    + COALESCE(
                        m6.incremental_revenue::double precision,
                        0.0
                    )
                    - COALESCE(
                        m6.incremental_cogs::double precision,
                        0.0
                    )
                    - COALESCE(
                        m6.inc006_allocated_marketing_cost::double precision,
                        0.0
                    )
                    - COALESCE(
                        m6.inc006_campaign_incentive_cost::double precision,
                        0.0
                    )
                    - (
                        COALESCE(
                            p.revenue::double precision,
                            0.0
                        )
                        * (
                            1.0
                            - COALESCE(
                                rc.recognized_revenue_multiplier::double precision,
                                1.0
                            )
                        )
                    )
                ) AS effective_contribution_profit

            FROM staging.order_profitability p
            LEFT JOIN staging.regional_capacity_overrides rc
              USING (order_id)
            LEFT JOIN staging.inc006_effective_marketing_economics m6
              USING (order_id);
            """,
        ),
        (
            "finance.daily_pnl",
            """
            DROP VIEW IF EXISTS finance.daily_pnl CASCADE;
            CREATE VIEW finance.daily_pnl AS
            SELECT *
            FROM staging.daily_pnl;
            """,
        ),

        # =====================================================================
        # MARKETING
        #
        # Important fix:
        # staging.marketing_campaigns has 11 columns while inc006_campaign has 10.
        # We therefore SELECT an explicit common canonical schema.
        # =====================================================================
        (
            "marketing.campaigns",
            """
            DROP VIEW IF EXISTS marketing.campaigns CASCADE;
            CREATE VIEW marketing.campaigns AS

            SELECT
                campaign_id,
                campaign_name,
                start_date,
                end_date,
                channel,
                objective,
                planned_budget,
                campaign_incentive_rate,
                source_type
            FROM staging.marketing_campaigns

            UNION ALL

            SELECT
                campaign_id,
                campaign_name,
                start_date,
                end_date,
                channel,
                objective,
                planned_budget,
                campaign_incentive_rate,
                source_type
            FROM staging.inc006_campaign;
            """,
        ),
        (
            "marketing.order_attribution",
            """
            DROP VIEW IF EXISTS marketing.order_attribution CASCADE;
            CREATE VIEW marketing.order_attribution AS
            SELECT *
            FROM staging.order_campaign_attribution;
            """,
        ),
        (
            "marketing.spend_daily",
            """
            DROP VIEW IF EXISTS marketing.spend_daily CASCADE;
            CREATE VIEW marketing.spend_daily AS
            SELECT *
            FROM staging.marketing_spend_daily;
            """,
        ),
        (
            "marketing.inc006_effective_economics",
            """
            DROP VIEW IF EXISTS marketing.inc006_effective_economics CASCADE;
            CREATE VIEW marketing.inc006_effective_economics AS
            SELECT *
            FROM staging.inc006_effective_marketing_economics;
            """,
        ),

        # =====================================================================
        # INVENTORY
        # =====================================================================
        (
            "inventory.weekly",
            """
            DROP VIEW IF EXISTS inventory.weekly CASCADE;
            CREATE VIEW inventory.weekly AS
            SELECT *
            FROM staging.inventory_weekly;
            """,
        ),
        (
            "inventory.stockout_events",
            """
            DROP VIEW IF EXISTS inventory.stockout_events CASCADE;
            CREATE VIEW inventory.stockout_events AS
            SELECT *
            FROM staging.stockout_events;
            """,
        ),
        (
            "inventory.effective_sales",
            """
            DROP VIEW IF EXISTS inventory.effective_sales CASCADE;
            CREATE VIEW inventory.effective_sales AS
            SELECT *
            FROM staging.inc007_effective_sales;
            """,
        ),

        # =====================================================================
        # CUSTOMER EXPERIENCE
        # =====================================================================
        (
            "cx.reviews",
            """
            DROP VIEW IF EXISTS cx.reviews CASCADE;
            CREATE VIEW cx.reviews AS
            SELECT *
            FROM staging.olist_order_reviews;
            """,
        ),
        (
            "cx.effective_reviews",
            """
            DROP VIEW IF EXISTS cx.effective_reviews CASCADE;
            CREATE VIEW cx.effective_reviews AS
            SELECT
                r.*,

                COALESCE(
                    cx.effective_review_score::double precision,
                    r.review_score::double precision
                ) AS effective_review_score,

                COALESCE(
                    cx.extra_delivery_delay_days::double precision,
                    0.0
                ) AS incident_extra_delivery_delay_days

            FROM staging.olist_order_reviews r
            LEFT JOIN staging.cx_incident_overrides cx
              USING (order_id);
            """,
        ),
        (
            "cx.returns",
            """
            DROP VIEW IF EXISTS cx.returns CASCADE;
            CREATE VIEW cx.returns AS
            SELECT *
            FROM staging.returns;
            """,
        ),

        # =====================================================================
        # GA4 BEHAVIOR
        # =====================================================================
        (
            "behavior.sessions",
            """
            DROP VIEW IF EXISTS behavior.sessions CASCADE;
            CREATE VIEW behavior.sessions AS
            SELECT *
            FROM staging.ga4_sessions;
            """,
        ),

        # =====================================================================
        # KNOWLEDGE / RETRIEVAL SOURCE
        # =====================================================================
        (
            "knowledge.documents",
            """
            DROP VIEW IF EXISTS knowledge.documents CASCADE;
            CREATE VIEW knowledge.documents AS
            SELECT
                document_id,
                filename,
                relative_path,
                content,
                source_type,
                trust_level
            FROM staging.documents;
            """,
        ),

        # =====================================================================
        # SEMANTIC / AGENT-FACING VIEWS
        # =====================================================================
        (
            "semantic.order_economics",
            """
            DROP VIEW IF EXISTS semantic.order_economics CASCADE;
            CREATE VIEW semantic.order_economics AS
            SELECT
                order_id,
                order_purchase_timestamp,
                revenue,
                cogs,
                contribution_profit,
                regional_revenue_multiplier,
                inc006_incremental_revenue,
                inc006_marketing_cost,
                inc006_incentive_cost,
                effective_revenue,
                effective_cogs,
                effective_contribution_profit
            FROM finance.order_profitability_effective;
            """,
        ),
        (
            "semantic.daily_commerce",
            """
            DROP VIEW IF EXISTS semantic.daily_commerce CASCADE;
            CREATE VIEW semantic.daily_commerce AS
            SELECT
                DATE(
                    NULLIF(
                        order_purchase_timestamp,
                        ''
                    )::timestamp
                ) AS business_date,

                COUNT(DISTINCT order_id) AS orders,

                SUM(
                    effective_revenue
                ) AS revenue,

                SUM(
                    effective_cogs
                ) AS cogs,

                SUM(
                    effective_contribution_profit
                ) AS contribution_profit,

                CASE
                    WHEN SUM(effective_revenue) = 0
                    THEN NULL
                    ELSE
                        SUM(effective_contribution_profit)
                        / SUM(effective_revenue)
                END AS contribution_margin

            FROM finance.order_profitability_effective
            GROUP BY 1;
            """,
        ),
        (
            "semantic.ga4_funnel_daily",
            """
            DROP VIEW IF EXISTS semantic.ga4_funnel_daily CASCADE;
            CREATE VIEW semantic.ga4_funnel_daily AS
            SELECT
                NULLIF(
                    session_date,
                    ''
                )::date AS session_date,

                COUNT(*) AS sessions,

                SUM(
                    CASE
                        WHEN COALESCE(
                            view_item_count::double precision,
                            0
                        ) > 0
                        THEN 1
                        ELSE 0
                    END
                ) AS product_view_sessions,

                SUM(
                    CASE
                        WHEN COALESCE(
                            add_to_cart_count::double precision,
                            0
                        ) > 0
                        THEN 1
                        ELSE 0
                    END
                ) AS add_to_cart_sessions,

                SUM(
                    CASE
                        WHEN COALESCE(
                            begin_checkout_count::double precision,
                            0
                        ) > 0
                        THEN 1
                        ELSE 0
                    END
                ) AS checkout_sessions,

                SUM(
                    CASE
                        WHEN COALESCE(
                            purchase_count::double precision,
                            0
                        ) > 0
                        THEN 1
                        ELSE 0
                    END
                ) AS purchase_sessions,

                SUM(
                    COALESCE(
                        purchase_revenue::double precision,
                        0
                    )
                ) AS purchase_revenue,

                AVG(
                    COALESCE(
                        did_purchase::double precision,
                        0
                    )
                ) AS purchase_session_rate,

                CASE
                    WHEN SUM(
                        CASE
                            WHEN COALESCE(
                                begin_checkout_count::double precision,
                                0
                            ) > 0
                            THEN 1
                            ELSE 0
                        END
                    ) = 0
                    THEN NULL

                    ELSE
                        SUM(
                            COALESCE(
                                did_checkout_abandon::double precision,
                                0
                            )
                        )
                        /
                        SUM(
                            CASE
                                WHEN COALESCE(
                                    begin_checkout_count::double precision,
                                    0
                                ) > 0
                                THEN 1
                                ELSE 0
                            END
                        )
                END AS checkout_abandon_rate

            FROM behavior.sessions
            GROUP BY 1;
            """,
        ),
        (
            "semantic.product_mix_effective",
            """
            DROP VIEW IF EXISTS semantic.product_mix_effective CASCADE;
            CREATE VIEW semantic.product_mix_effective AS
            SELECT *
            FROM staging.inc005_effective_mix_economics;
            """,
        ),
        (
            "semantic.stockout_effective_sales",
            """
            DROP VIEW IF EXISTS semantic.stockout_effective_sales CASCADE;
            CREATE VIEW semantic.stockout_effective_sales AS
            SELECT *
            FROM staging.inc007_effective_sales;
            """,
        ),
        (
            "semantic.misleading_correlation_fixture",
            """
            DROP VIEW IF EXISTS semantic.misleading_correlation_fixture CASCADE;
            CREATE VIEW semantic.misleading_correlation_fixture AS
            SELECT *
            FROM staging.inc012_misleading_correlation;
            """,
        ),
    ]

    with engine.begin() as conn:
        for name, sql in statements:
            try:
                execute_sql(conn, sql)
                print(f"[VIEW] {name}")
            except Exception as exc:
                print(f"\n[FAIL] while creating {name}")
                print(f"Error type: {type(exc).__name__}")
                print(f"Error: {exc}")
                raise

        # Agent is allowed to query canonical and semantic schemas.
        execute_sql(
            conn,
            """
            GRANT SELECT ON ALL TABLES IN SCHEMA
                commerce,
                catalog,
                operations,
                finance,
                marketing,
                inventory,
                cx,
                behavior,
                knowledge,
                semantic
            TO opslens_agent_reader;
            """,
        )

        # Agent must never query staging directly.
        execute_sql(
            conn,
            """
            REVOKE ALL
            ON SCHEMA staging
            FROM opslens_agent_reader;
            """,
        )

    print("\nPASS: canonical/effective views created.")


def write_manifest(root: Path, loaded: dict):
    path = root / "docs" / "phase2b_ingestion_manifest.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(loaded, indent=2),
        encoding="utf-8",
    )
    print("\nSaved ingestion manifest:")
    print(path)


def main():
    parser = argparse.ArgumentParser()

    parser.add_argument(
        "--project-root",
        default=".",
    )

    parser.add_argument(
        "--views-only",
        action="store_true",
        help=(
            "Skip CSV ingestion and only rebuild canonical/effective views. "
            "Use this when staging tables are already loaded."
        ),
    )

    args = parser.parse_args()
    root = Path(args.project_root).resolve()

    (
        raw_olist,
        synth,
        processed,
        docs,
        csv_sources,
    ) = paths_for(root)

    assert_runtime_manifest_safe(csv_sources)

    print("=" * 82)
    print("OPSLENS PHASE 2B — DETERMINISTIC DATA WORLD")
    print("=" * 82)
    print("Project root:", root)
    print("Mode:", "VIEWS ONLY" if args.views_only else "FULL LOAD + VIEWS")
    print(
        "Security boundary: data/eval_ground_truth is excluded from runtime."
    )

    loaded = {}

    if args.views_only:
        print("\nChecking existing staging tables...")
        require_staging_tables()
        print("PASS: required staging tables are present.")

    else:
        print("\nLoading staging tables...")

        for name, path in csv_sources.items():
            try:
                rows, cols = load_csv(name, path)

                loaded[name] = {
                    "rows": rows,
                    "cols": cols,
                    "path": str(path),
                }

            except Exception as exc:
                print(f"\n[FAIL] staging.{name}")
                print(f"Source: {path}")
                print(f"Error type: {type(exc).__name__}")
                print(f"Error: {exc}")
                raise

        document_rows = load_documents(root, docs)

        loaded["documents"] = {
            "rows": document_rows,
            "path": str(docs),
        }

        write_manifest(root, loaded)

    create_canonical_views()

    print("\n" + "=" * 82)
    print("PHASE 2B COMPLETE")
    print("=" * 82)
    print("Next command:")
    print("python scripts/validate_phase2b.py")


if __name__ == "__main__":
    main()
