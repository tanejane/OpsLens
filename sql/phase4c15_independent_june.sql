-- Independent direct PostgreSQL reference for June 2018; same documented metrics,
-- different expression strategy from MCP compiler. Returns one compact JSON object.
WITH q AS (
 SELECT order_id, order_purchase_time, effective_delivery_time, promised_delivery_time,
   delivery_days, is_late, duration_eligible, lateness_eligible
 FROM semantic.order_delivery_evidence_v1
 WHERE order_purchase_time >= DATE '2018-06-01' AND order_purchase_time < DATE '2018-07-01'
), counts AS (
 SELECT count(*)::int AS eligible_orders, count(DISTINCT order_id)::int AS distinct_orders,
  sum(CASE WHEN lateness_eligible THEN 1 ELSE 0 END)::int AS lateness_eligible_orders,
  sum(CASE WHEN is_late THEN 1 ELSE 0 END)::int AS late_orders,
  sum(CASE WHEN duration_eligible THEN 1 ELSE 0 END)::int AS duration_eligible_orders,
  sum(CASE WHEN effective_delivery_time IS NULL THEN 1 ELSE 0 END)::int AS missing_actual,
  sum(CASE WHEN promised_delivery_time IS NULL THEN 1 ELSE 0 END)::int AS missing_estimated,
  sum(CASE WHEN order_purchase_time IS NULL THEN 1 ELSE 0 END)::int AS missing_purchase,
  avg(CASE WHEN duration_eligible THEN delivery_days END) AS average_delivery_days
 FROM q
)
SELECT json_build_object('period',json_build_array('2018-06-01','2018-07-01'),
 'population',json_build_object('eligible_orders',eligible_orders,'lateness_eligible_orders',lateness_eligible_orders,'late_orders',late_orders,'duration_eligible_orders',duration_eligible_orders,'missing_actual',missing_actual,'missing_estimated',missing_estimated,'missing_purchase',missing_purchase),
 'metrics',json_build_object('late_delivery_rate',100.0*late_orders/NULLIF(lateness_eligible_orders,0),'average_delivery_days',average_delivery_days,'delivered_order_count',duration_eligible_orders,'delivery_evidence_coverage',100.0*lateness_eligible_orders/NULLIF(eligible_orders,0))) FROM counts;
