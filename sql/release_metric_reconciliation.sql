-- Evaluator-only. Bind start and finish as half-open purchase dates.
-- Independently reconstruct finance totals from staged inputs, never via dashboard views.
WITH base AS (
    SELECT * FROM staging.order_profitability
    WHERE order_purchase_timestamp::timestamp >= CAST(:start AS date)
      AND order_purchase_timestamp::timestamp < CAST(:finish AS date)
), joined AS (
    SELECT b.order_id, b.revenue, b.cogs, b.contribution_profit,
           coalesce(b.revenue,0) * coalesce(r.recognized_revenue_multiplier,1)
               + coalesce(m.incremental_revenue,0) AS rev,
           coalesce(b.cogs,0) + coalesce(m.incremental_cogs,0) AS cost,
           coalesce(b.contribution_profit,0) + coalesce(m.incremental_revenue,0)
               - coalesce(m.incremental_cogs,0) - coalesce(m.inc006_allocated_marketing_cost,0)
               - coalesce(m.inc006_campaign_incentive_cost,0)
               + coalesce(b.revenue,0)*(coalesce(r.recognized_revenue_multiplier,1)-1) AS profit,
           coalesce(b.refund_amount,0) AS refund, coalesce(b.fulfillment_cost,0) AS fulfillment,
           coalesce(b.payment_processing_cost,0) AS processing,
           coalesce(b.marketing_cost,0)+coalesce(m.inc006_allocated_marketing_cost,0) AS marketing,
           coalesce(b.campaign_incentive_cost,0)+coalesce(m.inc006_campaign_incentive_cost,0) AS incentive
    FROM base b LEFT JOIN staging.regional_capacity_overrides r USING(order_id)
    LEFT JOIN staging.inc006_effective_marketing_economics m USING(order_id)
)
SELECT (SELECT count(*) FROM base) AS base_rows, count(*) AS joined_rows,
       count(DISTINCT order_id) AS finance_orders,
       count(*) FILTER (WHERE revenue IS NULL OR cogs IS NULL OR contribution_profit IS NULL) AS missing_finance,
       sum(rev) AS revenue, sum(cost) AS effective_cogs, sum(profit) AS contribution_profit,
       100 * sum(profit)/nullif(sum(rev),0) AS contribution_margin_pct,
       sum(refund) AS refund_amount, sum(fulfillment) AS fulfillment_cost,
       sum(processing) AS payment_processing_cost, sum(marketing) AS marketing_cost_effective,
       sum(incentive) AS incentive_cost_effective,
       sum(rev-cost-profit-refund-fulfillment-processing-marketing-incentive) AS other_adjustments_residual,
       (SELECT count(DISTINCT order_id) FROM staging.olist_orders
        WHERE order_purchase_timestamp::timestamp >= CAST(:start AS date)
          AND order_purchase_timestamp::timestamp < CAST(:finish AS date)) AS orders
FROM joined
