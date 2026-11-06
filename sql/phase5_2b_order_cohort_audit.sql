-- Phase 5.2B: independent same-order-set validation. Run with database admin.
-- Read only; does not grant MCP access or join per-order operational outcomes.
-- Month cohort attribution comes from the underlying purchase timestamps.
WITH periods(month_start,month_end) AS (
 VALUES (DATE '2018-05-01',DATE '2018-06-01'),
        (DATE '2018-06-01',DATE '2018-07-01')
),
source_ids AS (
 SELECT p.month_start, o.order_id, o.order_purchase_timestamp::timestamp AS purchase_ts
 FROM periods p JOIN commerce.orders o
   ON o.order_purchase_timestamp::timestamp >= p.month_start
  AND o.order_purchase_timestamp::timestamp < p.month_end
),
delivery_ids AS (
 SELECT p.month_start, d.order_id, d.order_purchase_time::timestamp AS purchase_ts
 FROM periods p JOIN semantic.order_delivery_evidence_v1 d
   ON d.order_purchase_time::timestamp >= p.month_start
  AND d.order_purchase_time::timestamp < p.month_end
),
review_ids AS (
 SELECT p.month_start, r.order_id, r.purchase_time::timestamp AS purchase_ts
 FROM periods p JOIN semantic.order_review_evidence_v1 r
   ON r.purchase_time::timestamp >= p.month_start
  AND r.purchase_time::timestamp < p.month_end
),
per_period AS (
 SELECT p.month_start, p.month_end,
   (SELECT COUNT(*) FROM source_ids s WHERE s.month_start=p.month_start) AS source_rows,
   (SELECT COUNT(DISTINCT s.order_id) FROM source_ids s WHERE s.month_start=p.month_start) AS source_unique_orders,
   (SELECT COUNT(*) FROM delivery_ids d WHERE d.month_start=p.month_start) AS delivery_rows,
   (SELECT COUNT(DISTINCT d.order_id) FROM delivery_ids d WHERE d.month_start=p.month_start) AS delivery_unique_orders,
   (SELECT COUNT(*) FROM review_ids r WHERE r.month_start=p.month_start) AS review_rows,
   (SELECT COUNT(DISTINCT r.order_id) FROM review_ids r WHERE r.month_start=p.month_start) AS review_unique_orders,
   (SELECT COUNT(*) FROM (
      SELECT s.order_id FROM source_ids s WHERE s.month_start=p.month_start
      EXCEPT SELECT d.order_id FROM delivery_ids d WHERE d.month_start=p.month_start
   ) x) AS missing_delivery_orders,
   (SELECT COUNT(*) FROM (
      SELECT s.order_id FROM source_ids s WHERE s.month_start=p.month_start
      EXCEPT SELECT r.order_id FROM review_ids r WHERE r.month_start=p.month_start
   ) x) AS missing_review_orders,
   (SELECT COUNT(*) FROM (
      SELECT d.order_id FROM delivery_ids d WHERE d.month_start=p.month_start
      EXCEPT SELECT s.order_id FROM source_ids s WHERE s.month_start=p.month_start
   ) x) AS extra_delivery_orders,
   (SELECT COUNT(*) FROM (
      SELECT r.order_id FROM review_ids r WHERE r.month_start=p.month_start
      EXCEPT SELECT s.order_id FROM source_ids s WHERE s.month_start=p.month_start
   ) x) AS extra_review_orders,
   (SELECT COUNT(*) FROM (
      SELECT d.order_id FROM delivery_ids d WHERE d.month_start=p.month_start
      EXCEPT SELECT r.order_id FROM review_ids r WHERE r.month_start=p.month_start
   ) x) AS delivery_only_orders,
   (SELECT COUNT(*) FROM (
      SELECT r.order_id FROM review_ids r WHERE r.month_start=p.month_start
      EXCEPT SELECT d.order_id FROM delivery_ids d WHERE d.month_start=p.month_start
   ) x) AS review_only_orders,
   (SELECT COUNT(*) FROM source_ids s JOIN delivery_ids d
       ON s.order_id=d.order_id AND s.month_start=d.month_start
       WHERE s.month_start=p.month_start AND s.purchase_ts IS DISTINCT FROM d.purchase_ts
   ) AS delivery_purchase_timestamp_mismatches,
   (SELECT COUNT(*) FROM source_ids s JOIN review_ids r
       ON s.order_id=r.order_id AND s.month_start=r.month_start
       WHERE s.month_start=p.month_start AND s.purchase_ts IS DISTINCT FROM r.purchase_ts
   ) AS review_purchase_timestamp_mismatches
 FROM periods p
),
global_quality AS (
 SELECT
 (SELECT COUNT(*) FROM semantic.order_delivery_evidence_v1 WHERE order_id IS NULL) AS delivery_null_order_ids,
 (SELECT COUNT(*) FROM semantic.order_review_evidence_v1 WHERE order_id IS NULL) AS review_null_order_ids,
 (SELECT COUNT(*) FROM commerce.orders WHERE order_id IS NULL) AS source_null_order_ids,
 (SELECT COUNT(*) FROM (SELECT order_id FROM semantic.order_delivery_evidence_v1 GROUP BY order_id HAVING COUNT(*)>1) z) AS delivery_duplicate_order_ids,
 (SELECT COUNT(*) FROM (SELECT order_id FROM semantic.order_review_evidence_v1 GROUP BY order_id HAVING COUNT(*)>1) z) AS review_duplicate_order_ids,
 (SELECT COUNT(*) FROM (SELECT order_id FROM commerce.orders GROUP BY order_id HAVING COUNT(*)>1) z) AS source_duplicate_order_ids,
 (SELECT COUNT(*) FROM semantic.order_delivery_evidence_v1 WHERE order_purchase_time IS NULL) AS delivery_missing_purchase_time,
 (SELECT COUNT(*) FROM semantic.order_review_evidence_v1 WHERE purchase_time IS NULL) AS review_missing_purchase_time
)
SELECT json_build_object(
 'contract','PHASE5_2B_EXACT_ORDER_COHORT_V1',
 'time_basis','order_purchase_time',
 'month_pairs',json_agg(json_build_object(
   'month_start',p.month_start::text,'month_end',p.month_end::text,
   'source_rows',p.source_rows,'source_unique_orders',p.source_unique_orders,
   'delivery_rows',p.delivery_rows,'delivery_unique_orders',p.delivery_unique_orders,
   'review_rows',p.review_rows,'review_unique_orders',p.review_unique_orders,
   'missing_delivery_orders',p.missing_delivery_orders,
   'missing_review_orders',p.missing_review_orders,
   'extra_delivery_orders',p.extra_delivery_orders,
   'extra_review_orders',p.extra_review_orders,
   'delivery_only_orders',p.delivery_only_orders,
   'review_only_orders',p.review_only_orders,
   'delivery_purchase_timestamp_mismatches',p.delivery_purchase_timestamp_mismatches,
   'review_purchase_timestamp_mismatches',p.review_purchase_timestamp_mismatches
 ) ORDER BY p.month_start),
 'global_quality',(SELECT row_to_json(g) FROM global_quality g),
 'read_only',true,'approved_for_mcp',false,'causal_claim',false
)::text
FROM per_period p;
