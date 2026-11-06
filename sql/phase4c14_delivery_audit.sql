-- Independent raw-vs-view reconciliation and coverage; emits one JSON object.
BEGIN READ ONLY;
WITH raw AS (
 SELECT order_id,order_purchase_timestamp::timestamp AS p,
        final_effective_delivered_customer_date::timestamp AS a,
        order_estimated_delivery_date::timestamp AS e
 FROM operations.delivery_effective
),
raw_counts AS (
 SELECT COUNT(*)::bigint AS orders,COUNT(DISTINCT order_id)::bigint AS unique_orders,
        COUNT(*) FILTER (WHERE order_id IS NULL)::bigint AS null_keys,
        COUNT(*) FILTER (WHERE a IS NULL)::bigint AS missing_actual,
        COUNT(*) FILTER (WHERE e IS NULL)::bigint AS missing_estimated,
        COUNT(*) FILTER (WHERE p IS NULL)::bigint AS missing_purchase,
        COUNT(*) FILTER (WHERE a IS NOT NULL AND e IS NOT NULL)::bigint AS lateness_eligible,
        COUNT(*) FILTER (WHERE a IS NOT NULL AND e IS NOT NULL AND a>e)::bigint AS late_orders,
        COUNT(*) FILTER (WHERE a IS NOT NULL AND p IS NOT NULL AND a>=p)::bigint AS duration_eligible,
        COUNT(*) FILTER (WHERE a IS NOT NULL AND p IS NOT NULL AND a<p)::bigint AS negative_duration,
        ROUND(AVG(EXTRACT(EPOCH FROM a-p)/86400.0) FILTER (WHERE a IS NOT NULL AND p IS NOT NULL AND a>=p),8) AS mean_delivery_days
 FROM raw
),
view_counts AS (
 SELECT COUNT(*)::bigint AS orders,COUNT(DISTINCT order_id)::bigint AS unique_orders,
        COUNT(*) FILTER (WHERE order_id IS NULL)::bigint AS null_keys,
        COUNT(*) FILTER (WHERE effective_delivery_time IS NULL)::bigint AS missing_actual,
        COUNT(*) FILTER (WHERE promised_delivery_time IS NULL)::bigint AS missing_estimated,
        COUNT(*) FILTER (WHERE order_purchase_time IS NULL)::bigint AS missing_purchase,
        COUNT(*) FILTER (WHERE lateness_eligible)::bigint AS lateness_eligible,
        COUNT(*) FILTER (WHERE is_late IS TRUE)::bigint AS late_orders,
        COUNT(*) FILTER (WHERE duration_eligible)::bigint AS duration_eligible,
        COUNT(*) FILTER (WHERE effective_delivery_time < order_purchase_time)::bigint AS negative_duration,
        ROUND(AVG(delivery_days),8) AS mean_delivery_days,
        COUNT(*) FILTER (WHERE is_late IS NOT NULL AND NOT lateness_eligible)::bigint AS invalid_late_flags,
        COUNT(*) FILTER (WHERE delivery_days IS NOT NULL AND NOT duration_eligible)::bigint AS invalid_duration_values,
        COUNT(*) FILTER (WHERE lateness_eligible AND is_late IS NULL)::bigint AS missing_eligible_flags,
        COUNT(*) FILTER (WHERE duration_eligible AND delivery_days IS NULL)::bigint AS missing_eligible_duration
 FROM semantic.order_delivery_evidence_v1
),
monthly AS (
 SELECT COUNT(*)::bigint AS month_rows,
        COUNT(DISTINCT date_trunc('month',order_purchase_time))::bigint AS distinct_months,
        COUNT(*) FILTER (WHERE order_purchase_time IS NULL)::bigint AS missing_purchase_rows
 FROM semantic.order_delivery_evidence_v1
)
SELECT json_build_object('audit_version','4c14.1','source','operations.delivery_effective',
 'view','semantic.order_delivery_evidence_v1','policy','late_iff_actual_gt_estimated_on_eligible_orders',
 'time_basis','order_purchase_time','read_only',true,
 'raw',row_to_json(raw_counts),'derived',row_to_json(view_counts),
 'monthly',row_to_json(monthly),'mcp_approved',false)::text
FROM raw_counts CROSS JOIN view_counts CROSS JOIN monthly;
COMMIT;
