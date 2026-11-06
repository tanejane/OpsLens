-- Source-order population and denominators computed independently of the MCP views.
WITH cohort AS (
    SELECT * FROM staging.olist_orders WHERE order_purchase_timestamp::timestamp >= CAST(:start AS date)
        AND order_purchase_timestamp::timestamp < CAST(:finish AS date)
), delivery AS (
    SELECT o.order_id, nullif(o.order_estimated_delivery_date,'')::timestamp AS promised,
        coalesce(nullif(d.effective_delivered_customer_date,'')::timestamp,
                 nullif(o.order_delivered_customer_date,'')::timestamp)
        + make_interval(days => coalesce(r.extra_delivery_delay_days::numeric,0)::int)
        + make_interval(days => coalesce(c.extra_delivery_delay_days::numeric,0)::int) AS delivered
    FROM cohort o LEFT JOIN staging.effective_delivery_dates d USING(order_id)
    LEFT JOIN staging.regional_capacity_overrides r USING(order_id)
    LEFT JOIN staging.cx_incident_overrides c USING(order_id)
), reviews AS (
    SELECT o.order_id, avg(coalesce(c.effective_review_score::numeric,r.review_score::numeric)) AS score
    FROM cohort o JOIN staging.olist_order_reviews r USING(order_id)
    LEFT JOIN staging.cx_incident_overrides c USING(order_id) GROUP BY o.order_id
)
SELECT count(*) AS delivery_rows, count(DISTINCT order_id) AS delivery_orders,
       count(*) FILTER (WHERE delivered > promised) AS late_orders,
       count(delivered > promised) AS lateness_eligible,
       100.0 * count(*) FILTER (WHERE delivered > promised)/nullif(count(delivered > promised),0) AS late_delivery_rate,
       (SELECT count(score) FROM reviews) AS reviewed_orders,
       (SELECT avg(score) FROM reviews) AS average_review_score
FROM delivery
