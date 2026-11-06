-- Phase 4C.14: read-only-facing order-grain delivery evidence; no grants.
-- Based on previously audited operations.delivery_effective (one row per order).
BEGIN;
CREATE OR REPLACE VIEW semantic.order_delivery_evidence_v1 AS
WITH typed AS (
 SELECT order_id,
        order_purchase_timestamp::timestamp AS purchase_ts,
        final_effective_delivered_customer_date::timestamp AS delivered_ts,
        order_estimated_delivery_date::timestamp AS estimated_ts
 FROM operations.delivery_effective
)
SELECT order_id, purchase_ts AS order_purchase_time, delivered_ts AS effective_delivery_time,
       estimated_ts AS promised_delivery_time,
       (purchase_ts IS NOT NULL AND delivered_ts IS NOT NULL AND delivered_ts >= purchase_ts) AS duration_eligible,
       (delivered_ts IS NOT NULL AND estimated_ts IS NOT NULL) AS lateness_eligible,
       CASE WHEN delivered_ts IS NOT NULL AND estimated_ts IS NOT NULL
            THEN delivered_ts > estimated_ts ELSE NULL END AS is_late,
       CASE WHEN purchase_ts IS NOT NULL AND delivered_ts IS NOT NULL AND delivered_ts >= purchase_ts
            THEN EXTRACT(EPOCH FROM delivered_ts - purchase_ts)/86400.0 ELSE NULL END AS delivery_days,
       CASE WHEN delivered_ts IS NOT NULL AND estimated_ts IS NOT NULL
            THEN GREATEST(EXTRACT(EPOCH FROM delivered_ts - estimated_ts)/86400.0,0) ELSE NULL END AS late_days
FROM typed;
COMMENT ON VIEW semantic.order_delivery_evidence_v1 IS
 'Phase 4C.14 proposed governed delivery evidence: purchase-time cohorts, incident-adjusted actual dates, null-excluded lateness denominator; NOT MCP approved';
COMMIT;
