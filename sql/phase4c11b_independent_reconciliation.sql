-- Read-only independent metric audit, June 2018 purchase cohort.
-- The review evidence view has already passed Phase 4C.10 global grain checks.
-- Do not interpret a successful direct DB query as MCP allowlist authorization.
WITH cohort AS (
 SELECT order_id, has_review, low_rating, review_records, order_score
 FROM semantic.order_review_evidence_v1
 WHERE purchase_time >= DATE '2018-06-01'
   AND purchase_time < DATE '2018-07-01'
), audit AS (
 SELECT count(*)::bigint AS eligible_orders,
   count(DISTINCT order_id)::bigint AS distinct_orders,
   count(*) FILTER (WHERE has_review)::bigint AS reviewed_orders,
   count(*) FILTER (WHERE low_rating)::bigint AS low_rating_orders,
   count(*) FILTER (WHERE review_records > 1)::bigint AS multi_review_orders,
   avg(order_score) FILTER (WHERE has_review) AS average_review_score,
   100.0 * count(*) FILTER (WHERE low_rating) / NULLIF(count(*) FILTER (WHERE has_review),0) AS low_rating_rate,
   100.0 * count(*) FILTER (WHERE has_review) / NULLIF(count(*),0) AS review_coverage
 FROM cohort
)
SELECT row_to_json(audit) FROM audit;
