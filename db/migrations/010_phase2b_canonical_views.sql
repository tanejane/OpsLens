-- OpsLens Phase 2B canonical/effective runtime views.
-- Hidden evaluator truth is intentionally absent.

-- ---------- COMMERCE ----------
DROP VIEW IF EXISTS commerce.customers CASCADE;
CREATE VIEW commerce.customers AS
SELECT * FROM staging.olist_customers;

DROP VIEW IF EXISTS commerce.orders CASCADE;
CREATE VIEW commerce.orders AS
SELECT * FROM staging.olist_orders;

DROP VIEW IF EXISTS commerce.order_items CASCADE;
CREATE VIEW commerce.order_items AS
SELECT * FROM staging.olist_order_items;

DROP VIEW IF EXISTS commerce.payments CASCADE;
CREATE VIEW commerce.payments AS
SELECT * FROM staging.olist_order_payments;

-- ---------- CATALOG ----------
DROP VIEW IF EXISTS catalog.products CASCADE;
CREATE VIEW catalog.products AS
SELECT
  p.*,
  COALESCE(t.product_category_name_english, p.product_category_name, 'unknown') AS category
FROM staging.olist_products p
LEFT JOIN staging.product_category_translation t
  ON p.product_category_name = t.product_category_name;

-- ---------- OPERATIONS ----------
DROP VIEW IF EXISTS operations.sellers CASCADE;
CREATE VIEW operations.sellers AS
SELECT * FROM staging.olist_sellers;

DROP VIEW IF EXISTS operations.delivery_effective CASCADE;
CREATE VIEW operations.delivery_effective AS
SELECT
  o.order_id,
  o.order_purchase_timestamp,
  o.order_delivered_customer_date AS baseline_delivered_customer_date,
  o.order_estimated_delivery_date,
  COALESCE(
    ed.effective_delivered_customer_date,
    o.order_delivered_customer_date
  ) AS effective_delivered_customer_date,
  COALESCE(ed.extra_delay_days, 0) AS inc004_extra_delay_days,
  COALESCE(rc.extra_delivery_delay_days, 0) AS inc002_extra_delay_days,
  COALESCE(cx.extra_delivery_delay_days, 0) AS inc008_extra_delay_days,
  COALESCE(rc.capacity_impact, 'none') AS regional_capacity_impact,
  CASE
    WHEN COALESCE(
      ed.effective_delivered_customer_date,
      o.order_delivered_customer_date
    ) IS NULL THEN NULL
    ELSE (
      COALESCE(ed.effective_delivered_customer_date, o.order_delivered_customer_date)::timestamp
      + make_interval(days => COALESCE(rc.extra_delivery_delay_days, 0)::int)
      + make_interval(days => COALESCE(cx.extra_delivery_delay_days, 0)::int)
    )
  END AS final_effective_delivered_customer_date
FROM staging.olist_orders o
LEFT JOIN staging.effective_delivery_dates ed USING (order_id)
LEFT JOIN staging.regional_capacity_overrides rc USING (order_id)
LEFT JOIN staging.cx_incident_overrides cx USING (order_id);

-- ---------- FINANCE ----------
DROP VIEW IF EXISTS finance.order_profitability_base CASCADE;
CREATE VIEW finance.order_profitability_base AS
SELECT * FROM staging.order_profitability;

DROP VIEW IF EXISTS finance.order_profitability_effective CASCADE;
CREATE VIEW finance.order_profitability_effective AS
SELECT
  p.*,
  COALESCE(rc.recognized_revenue_multiplier, 1.0) AS regional_revenue_multiplier,
  COALESCE(m6.incremental_revenue, 0.0) AS inc006_incremental_revenue,
  COALESCE(m6.incremental_cogs, 0.0) AS inc006_incremental_cogs,
  COALESCE(m6.inc006_allocated_marketing_cost, 0.0) AS inc006_marketing_cost,
  COALESCE(m6.inc006_campaign_incentive_cost, 0.0) AS inc006_incentive_cost,
  (
    COALESCE(p.revenue, 0.0) * COALESCE(rc.recognized_revenue_multiplier, 1.0)
    + COALESCE(m6.incremental_revenue, 0.0)
  ) AS effective_revenue,
  (
    COALESCE(p.cogs, 0.0)
    + COALESCE(m6.incremental_cogs, 0.0)
  ) AS effective_cogs,
  (
    COALESCE(p.contribution_profit, 0.0)
    + COALESCE(m6.incremental_revenue, 0.0)
    - COALESCE(m6.incremental_cogs, 0.0)
    - COALESCE(m6.inc006_allocated_marketing_cost, 0.0)
    - COALESCE(m6.inc006_campaign_incentive_cost, 0.0)
    - (
        COALESCE(p.revenue, 0.0)
        * (1.0 - COALESCE(rc.recognized_revenue_multiplier, 1.0))
      )
  ) AS effective_contribution_profit
FROM staging.order_profitability p
LEFT JOIN staging.regional_capacity_overrides rc USING (order_id)
LEFT JOIN staging.inc006_effective_marketing_economics m6 USING (order_id);

DROP VIEW IF EXISTS finance.daily_pnl CASCADE;
CREATE VIEW finance.daily_pnl AS
SELECT * FROM staging.daily_pnl;

-- ---------- MARKETING ----------
DROP VIEW IF EXISTS marketing.campaigns CASCADE;
CREATE VIEW marketing.campaigns AS
SELECT * FROM staging.marketing_campaigns
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

DROP VIEW IF EXISTS marketing.order_attribution CASCADE;
CREATE VIEW marketing.order_attribution AS
SELECT * FROM staging.order_campaign_attribution;

DROP VIEW IF EXISTS marketing.spend_daily CASCADE;
CREATE VIEW marketing.spend_daily AS
SELECT * FROM staging.marketing_spend_daily;

DROP VIEW IF EXISTS marketing.inc006_effective_economics CASCADE;
CREATE VIEW marketing.inc006_effective_economics AS
SELECT * FROM staging.inc006_effective_marketing_economics;

-- ---------- INVENTORY ----------
DROP VIEW IF EXISTS inventory.weekly CASCADE;
CREATE VIEW inventory.weekly AS
SELECT * FROM staging.inventory_weekly;

DROP VIEW IF EXISTS inventory.stockout_events CASCADE;
CREATE VIEW inventory.stockout_events AS
SELECT * FROM staging.stockout_events;

DROP VIEW IF EXISTS inventory.effective_sales CASCADE;
CREATE VIEW inventory.effective_sales AS
SELECT * FROM staging.inc007_effective_sales;

-- ---------- CX ----------
DROP VIEW IF EXISTS cx.reviews CASCADE;
CREATE VIEW cx.reviews AS
SELECT * FROM staging.olist_order_reviews;

DROP VIEW IF EXISTS cx.effective_reviews CASCADE;
CREATE VIEW cx.effective_reviews AS
SELECT
  r.*,
  COALESCE(cx.effective_review_score, r.review_score::double precision) AS effective_review_score,
  COALESCE(cx.extra_delivery_delay_days, 0) AS incident_extra_delivery_delay_days
FROM staging.olist_order_reviews r
LEFT JOIN staging.cx_incident_overrides cx USING (order_id);

DROP VIEW IF EXISTS cx.returns CASCADE;
CREATE VIEW cx.returns AS
SELECT * FROM staging.returns;

-- ---------- BEHAVIOR ----------
DROP VIEW IF EXISTS behavior.sessions CASCADE;
CREATE VIEW behavior.sessions AS
SELECT * FROM staging.ga4_sessions;

-- ---------- KNOWLEDGE ----------
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

-- ---------- SEMANTIC / AGENT-FACING ----------
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

DROP VIEW IF EXISTS semantic.daily_commerce CASCADE;
CREATE VIEW semantic.daily_commerce AS
SELECT
  DATE(order_purchase_timestamp::timestamp) AS business_date,
  COUNT(DISTINCT order_id) AS orders,
  SUM(effective_revenue) AS revenue,
  SUM(effective_cogs) AS cogs,
  SUM(effective_contribution_profit) AS contribution_profit,
  CASE
    WHEN SUM(effective_revenue) = 0 THEN NULL
    ELSE SUM(effective_contribution_profit) / SUM(effective_revenue)
  END AS contribution_margin
FROM finance.order_profitability_effective
GROUP BY 1;

DROP VIEW IF EXISTS semantic.ga4_funnel_daily CASCADE;
CREATE VIEW semantic.ga4_funnel_daily AS
SELECT
  session_date::date AS session_date,
  COUNT(*) AS sessions,
  SUM(CASE WHEN COALESCE(view_item_count,0) > 0 THEN 1 ELSE 0 END) AS product_view_sessions,
  SUM(CASE WHEN COALESCE(add_to_cart_count,0) > 0 THEN 1 ELSE 0 END) AS add_to_cart_sessions,
  SUM(CASE WHEN COALESCE(begin_checkout_count,0) > 0 THEN 1 ELSE 0 END) AS checkout_sessions,
  SUM(CASE WHEN COALESCE(purchase_count,0) > 0 THEN 1 ELSE 0 END) AS purchase_sessions,
  SUM(COALESCE(purchase_revenue,0)) AS purchase_revenue,
  AVG(COALESCE(did_purchase,0)) AS purchase_session_rate,
  CASE
    WHEN SUM(CASE WHEN COALESCE(begin_checkout_count,0) > 0 THEN 1 ELSE 0 END) = 0 THEN NULL
    ELSE
      SUM(COALESCE(did_checkout_abandon,0))::double precision
      / SUM(CASE WHEN COALESCE(begin_checkout_count,0) > 0 THEN 1 ELSE 0 END)
  END AS checkout_abandon_rate
FROM behavior.sessions
GROUP BY 1;

DROP VIEW IF EXISTS semantic.product_mix_effective CASCADE;
CREATE VIEW semantic.product_mix_effective AS
SELECT * FROM staging.inc005_effective_mix_economics;

DROP VIEW IF EXISTS semantic.stockout_effective_sales CASCADE;
CREATE VIEW semantic.stockout_effective_sales AS
SELECT * FROM staging.inc007_effective_sales;

DROP VIEW IF EXISTS semantic.misleading_correlation_fixture CASCADE;
CREATE VIEW semantic.misleading_correlation_fixture AS
SELECT * FROM staging.inc012_misleading_correlation;

-- Agent reader: canonical/semantic only, no staging.
GRANT SELECT ON ALL TABLES IN SCHEMA
  commerce, catalog, operations, finance, marketing,
  inventory, cx, behavior, knowledge, semantic
TO opslens_agent_reader;

REVOKE ALL ON SCHEMA staging FROM opslens_agent_reader;
