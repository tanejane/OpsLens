-- Evaluator-only purchase-month denominator with all linked return events.
WITH orders AS (
    SELECT DISTINCT order_id FROM staging.olist_orders
    WHERE order_purchase_timestamp::timestamp >= CAST(:start AS date)
      AND order_purchase_timestamp::timestamp < CAST(:finish AS date)
), per_order AS (
    SELECT o.order_id, count(r.return_id) AS events, sum(r.refund_amount::numeric) AS amount
    FROM orders o LEFT JOIN staging.returns r USING (order_id) GROUP BY o.order_id
)
SELECT count(*) AS orders, count(*) FILTER (WHERE events>0) AS returned_orders,
       count(*) FILTER (WHERE amount>0) AS refunded_orders,
       coalesce(sum(events),0) AS events, coalesce(sum(amount),0) AS refund_amount
FROM per_order
