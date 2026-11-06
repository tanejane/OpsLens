-- Read-only operational evidence audit. No CREATE/UPDATE/GRANT.
-- Run against the existing OpsLens PostgreSQL, using psql -X -q -t -A.
BEGIN READ ONLY;
WITH
orders AS (
 SELECT COUNT(*)::bigint AS rows, COUNT(DISTINCT order_id)::bigint AS unique_orders,
        COUNT(*) FILTER (WHERE order_id IS NULL)::bigint AS null_keys
 FROM commerce.orders
),
delivery AS (
 SELECT COUNT(*)::bigint AS rows, COUNT(DISTINCT order_id)::bigint AS unique_orders,
        COUNT(*) FILTER (WHERE order_id IS NULL)::bigint AS null_keys,
        COUNT(*) FILTER (WHERE final_effective_delivered_customer_date IS NULL)::bigint AS missing_delivered,
        COUNT(*) FILTER (WHERE order_estimated_delivery_date IS NULL)::bigint AS missing_estimated,
        COUNT(*) FILTER (WHERE order_purchase_timestamp IS NULL)::bigint AS missing_purchased,
        COUNT(*) FILTER (WHERE final_effective_delivered_customer_date IS NOT NULL AND order_estimated_delivery_date IS NOT NULL AND final_effective_delivered_customer_date::timestamp > order_estimated_delivery_date::timestamp)::bigint AS late_observed,
        COUNT(*) FILTER (WHERE final_effective_delivered_customer_date IS NOT NULL AND order_purchase_timestamp IS NOT NULL AND final_effective_delivered_customer_date::timestamp < order_purchase_timestamp::timestamp)::bigint AS negative_elapsed
 FROM operations.delivery_effective
),
reviews AS (
 SELECT COUNT(*)::bigint AS rows, COUNT(DISTINCT order_id)::bigint AS unique_orders,
        COUNT(*) FILTER (WHERE order_id IS NULL)::bigint AS null_keys,
        COUNT(*) FILTER (WHERE effective_review_score IS NULL)::bigint AS missing_score,
        COUNT(*) FILTER (WHERE effective_review_score IS NOT NULL AND (effective_review_score < 1 OR effective_review_score > 5))::bigint AS out_of_range_score,
        COUNT(*) FILTER (WHERE review_score IS NOT NULL AND (review_score::numeric < 1 OR review_score::numeric > 5))::bigint AS out_of_range_raw_score
 FROM cx.effective_reviews
),
review_orphans AS (
 SELECT COUNT(*)::bigint AS rows
 FROM cx.effective_reviews r LEFT JOIN commerce.orders o ON r.order_id=o.order_id
 WHERE o.order_id IS NULL
),
delivery_orphans AS (
 SELECT COUNT(*)::bigint AS rows
 FROM operations.delivery_effective d LEFT JOIN commerce.orders o ON d.order_id=o.order_id
 WHERE o.order_id IS NULL
),
review_counts AS (
 SELECT COUNT(*)::bigint AS multi_review_orders, COALESCE(MAX(n),0)::bigint AS max_reviews_per_order
 FROM (SELECT order_id, COUNT(*) AS n FROM cx.effective_reviews GROUP BY order_id HAVING COUNT(*)>1) x
),
coverage AS (
 SELECT COUNT(DISTINCT d.order_id)::bigint AS reviewed_delivered_orders
 FROM operations.delivery_effective d JOIN cx.effective_reviews r ON d.order_id=r.order_id
 WHERE d.final_effective_delivered_customer_date IS NOT NULL AND r.effective_review_score IS NOT NULL
)
SELECT json_build_object(
 'audit_version','4c9.1',
 'source_views',json_build_array('commerce.orders','operations.delivery_effective','cx.effective_reviews'),
 'orders',row_to_json(orders), 'delivery',row_to_json(delivery), 'reviews',row_to_json(reviews),
 'review_orphans', (SELECT rows FROM review_orphans),
 'delivery_orphans', (SELECT rows FROM delivery_orphans),
 'review_cardinality',row_to_json(review_counts),
 'coverage',row_to_json(coverage),
 'scope','observed review and delivery fields include controlled incident overrides; no causal interpretation',
 'query_type','read_only'
)::text
FROM orders CROSS JOIN delivery CROSS JOIN reviews CROSS JOIN review_counts CROSS JOIN coverage;
COMMIT;
