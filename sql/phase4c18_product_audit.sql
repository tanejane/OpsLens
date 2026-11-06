-- Phase 4C.18: read-only product/category source and relationship audit.
-- No metric authorization or inventory inference. One JSON object is emitted.
WITH
orders AS (
 SELECT COUNT(*)::bigint n, COUNT(DISTINCT order_id)::bigint unique_ids,
        COUNT(*) FILTER (WHERE order_id IS NULL)::bigint null_keys
 FROM commerce.orders
),
items AS (
 SELECT COUNT(*)::bigint n,
        COUNT(DISTINCT (order_id,order_item_id))::bigint unique_keys,
        COUNT(*) FILTER (WHERE order_id IS NULL OR order_item_id IS NULL)::bigint null_keys,
        COUNT(*) FILTER (WHERE product_id IS NULL)::bigint missing_product_id,
        COUNT(*) FILTER (WHERE price IS NULL OR price::numeric < 0)::bigint invalid_price,
        COUNT(*) FILTER (WHERE freight_value IS NULL OR freight_value::numeric < 0)::bigint invalid_freight,
        COUNT(DISTINCT order_id)::bigint orders_with_items,
        SUM(price::numeric) AS item_price_sum
 FROM commerce.order_items
),
products AS (
 SELECT COUNT(*)::bigint n, COUNT(DISTINCT product_id)::bigint unique_ids,
        COUNT(*) FILTER (WHERE product_id IS NULL)::bigint null_keys,
        COUNT(*) FILTER (WHERE product_category_name IS NULL OR btrim(product_category_name) = '')::bigint missing_category
 FROM catalog.products
),
relationships AS (
 SELECT COUNT(*) FILTER (WHERE o.order_id IS NULL)::bigint orphan_items,
        COUNT(*) FILTER (WHERE p.product_id IS NULL)::bigint unknown_products,
        COUNT(*) FILTER (WHERE p.product_id IS NOT NULL AND (p.product_category_name IS NULL OR btrim(p.product_category_name) = ''))::bigint items_missing_category,
        COUNT(*)::bigint joined_item_rows,
        COUNT(DISTINCT (i.order_id,i.order_item_id))::bigint joined_unique_item_keys
 FROM commerce.order_items i
 LEFT JOIN commerce.orders o ON o.order_id = i.order_id
 LEFT JOIN catalog.products p ON p.product_id = i.product_id
),
coverage AS (
 SELECT COUNT(*) FILTER (WHERE order_purchase_timestamp IS NULL)::bigint missing_purchase,
        MIN(order_purchase_timestamp::timestamp)::text AS min_purchase,
        MAX(order_purchase_timestamp::timestamp)::text AS max_purchase
 FROM commerce.orders
),
months AS (
 SELECT COUNT(*)::bigint month_count FROM (
   SELECT date_trunc('month',o.order_purchase_timestamp::timestamp) AS period
   FROM commerce.orders o JOIN commerce.order_items i ON i.order_id=o.order_id
   GROUP BY 1
 ) x
)
SELECT json_build_object(
 'audit_version','4C18_V1',
 'sources',json_build_object('orders','commerce.orders','items','commerce.order_items','products','catalog.products'),
 'orders', (SELECT row_to_json(orders) FROM orders),
 'items', (SELECT row_to_json(items) FROM items),
 'products', (SELECT row_to_json(products) FROM products),
 'relationships', (SELECT row_to_json(relationships) FROM relationships),
 'coverage', (SELECT row_to_json(coverage) FROM coverage),
 'purchase_months_with_items', (SELECT month_count FROM months),
 'audit_only',true,'approved_for_mcp',false,'inventory_evidence_available',false,'causal_claim',false
)::text;
