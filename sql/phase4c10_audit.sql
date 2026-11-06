BEGIN READ ONLY;
WITH s AS (
 SELECT COUNT(*)::bigint orders, COUNT(DISTINCT order_id)::bigint unique_orders FROM commerce.orders
), r AS (
 SELECT COUNT(*)::bigint review_rows, COUNT(*) FILTER (WHERE effective_review_score IS NOT NULL AND
 (effective_review_score::numeric < 1 OR effective_review_score::numeric > 5))::bigint bad_scores,
 COUNT(DISTINCT order_id)::bigint reviewed_ids FROM cx.effective_reviews
), p AS (
 SELECT order_id, COUNT(*)::bigint n, COUNT(effective_review_score)::bigint scored,
 AVG(effective_review_score::numeric) AS avg_score
 FROM cx.effective_reviews GROUP BY order_id
), v AS (
 SELECT COUNT(*)::bigint rows, COUNT(DISTINCT x.order_id)::bigint unique_rows,
 COUNT(*) FILTER (WHERE x.order_id IS NULL)::bigint null_keys,
 COUNT(*) FILTER (WHERE x.purchase_time IS NULL)::bigint missing_purchase_dates,
 COUNT(*) FILTER (WHERE x.has_review)::bigint reviewed_orders,
 COUNT(*) FILTER (WHERE x.low_rating)::bigint low_rating_orders,
 COUNT(*) FILTER (WHERE x.review_records > 1)::bigint multiple_review_orders,
 COALESCE(SUM(x.review_records),0)::bigint aggregated_review_rows,
 COUNT(*) FILTER (WHERE x.order_score IS DISTINCT FROM p.avg_score
  OR x.review_records IS DISTINCT FROM p.n OR x.valid_score_records IS DISTINCT FROM p.scored)::bigint mismatched_scores,
 COUNT(*) FILTER (WHERE x.has_review IS DISTINCT FROM COALESCE(p.scored > 0, false)
  OR x.low_rating IS DISTINCT FROM COALESCE(p.scored > 0 AND p.avg_score <= 2, false))::bigint mismatched_flags
 FROM semantic.order_review_evidence_v1 x LEFT JOIN p ON x.order_id=p.order_id
), m AS (
 SELECT COALESCE(json_agg(row_to_json(z) ORDER BY z.month), '[]'::json) months FROM (
 SELECT to_char(date_trunc('month',purchase_time),'YYYY-MM') AS "month",
 COUNT(*)::bigint orders, COUNT(*) FILTER (WHERE has_review)::bigint reviewed_orders,
 COUNT(*) FILTER (WHERE low_rating)::bigint low_rating_orders,
 AVG(order_score) FILTER (WHERE has_review)::numeric(12,6) average_score
 FROM semantic.order_review_evidence_v1 WHERE purchase_time IS NOT NULL GROUP BY 1
 ) z
)
SELECT json_build_object('version','4c10.1','read_only',true,'mcp_authorized',false,
 'policy','mean_non_null_effective_scores_per_order','time_basis','purchase_month',
 'source',row_to_json(s),'reviews',row_to_json(r),'evidence',row_to_json(v),'months',m.months)::text
FROM s CROSS JOIN r CROSS JOIN v CROSS JOIN m;
COMMIT;

