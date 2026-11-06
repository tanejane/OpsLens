-- Independent purchase-month category reconciliation, raw commerce tables.
-- Fixed June 2018, beleza_saude; explicit Unknown bucket.
WITH base AS (
 SELECT i.order_id, i.order_item_id,
        COALESCE(NULLIF(btrim(p.product_category_name), ''),'Unknown')::text AS category,
        i.price::numeric AS item_price, i.freight_value::numeric AS freight_value
 FROM commerce.order_items i
 JOIN commerce.orders o ON o.order_id=i.order_id
 LEFT JOIN catalog.products p ON p.product_id=i.product_id
 WHERE o.order_purchase_timestamp::timestamp >= DATE '2018-06-01'
   AND o.order_purchase_timestamp::timestamp < DATE '2018-07-01'
), totals AS (
 SELECT COUNT(*)::bigint AS total_units,
 COUNT(DISTINCT (order_id,order_item_id))::bigint AS unique_items,
 COUNT(DISTINCT order_id)::bigint AS total_orders,
 COALESCE(SUM(item_price),0)::numeric AS total_gmv,
 COUNT(*) FILTER(WHERE item_price IS NULL OR item_price < 0 OR freight_value IS NULL OR freight_value < 0)::bigint AS invalid_items
 FROM base
), selected AS (
 SELECT COUNT(*)::bigint AS category_units,
 COUNT(DISTINCT (order_id,order_item_id))::bigint AS category_unique_items,
 COUNT(DISTINCT order_id)::bigint AS category_orders,
 COALESCE(SUM(item_price),0)::numeric AS category_gmv,
 COUNT(*) FILTER(WHERE item_price IS NULL OR item_price < 0 OR freight_value IS NULL OR freight_value < 0)::bigint AS category_invalid_items
 FROM base WHERE category='beleza_saude'
)
SELECT row_to_json(x) FROM (
 SELECT totals.*, selected.* FROM totals CROSS JOIN selected
) x;

