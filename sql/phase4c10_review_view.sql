-- One row per order; effective scores may include modeled incident adjustments.
-- No grants or changes to existing views.
BEGIN;
CREATE OR REPLACE VIEW semantic.order_review_evidence_v1 AS
WITH per_order AS (
 SELECT order_id, COUNT(*)::bigint AS review_records,
        COUNT(effective_review_score)::bigint AS valid_score_records,
        AVG(effective_review_score::numeric) AS order_score,
        MIN(effective_review_score::numeric) AS min_score,
        MAX(effective_review_score::numeric) AS max_score
 FROM cx.effective_reviews GROUP BY order_id
)
SELECT o.order_id, o.order_purchase_timestamp::timestamp AS purchase_time,
       r.review_records, r.valid_score_records, r.order_score, r.min_score, r.max_score,
       COALESCE(r.valid_score_records > 0, false) AS has_review,
       COALESCE(r.valid_score_records > 0 AND r.order_score <= 2, false) AS low_rating
FROM commerce.orders o LEFT JOIN per_order r ON o.order_id=r.order_id;
COMMENT ON VIEW semantic.order_review_evidence_v1 IS 'Audit-only. Purchase-cohort, mean of non-null effective scores per order. No MCP authorization.';
COMMIT;
