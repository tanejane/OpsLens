-- Independent month-level source-to-view reconciliation; emits one JSON object.
WITH raw AS (
 SELECT COUNT(*)::bigint units, COUNT(DISTINCT (i.order_id,i.order_item_id))::bigint keys,
 COALESCE(SUM(i.price::numeric),0) gmv,
 COUNT(*) FILTER (WHERE p.product_category_name IS NULL OR btrim(p.product_category_name)='')::bigint unknown_units
 FROM commerce.order_items i JOIN commerce.orders o ON o.order_id=i.order_id
 LEFT JOIN catalog.products p ON p.product_id=i.product_id
 WHERE o.order_purchase_timestamp::timestamp >= DATE '2018-06-01' AND o.order_purchase_timestamp::timestamp < DATE '2018-07-01'
), derived AS (
 SELECT COUNT(*)::bigint units,COUNT(DISTINCT (order_id,order_item_id))::bigint keys,
 COALESCE(SUM(item_price),0) gmv,
 COUNT(*) FILTER (WHERE category='Unknown')::bigint unknown_units
 FROM semantic.order_item_product_evidence_v1
 WHERE order_purchase_time >= DATE '2018-06-01' AND order_purchase_time < DATE '2018-07-01'
), monthly AS (
 SELECT date_trunc('month',order_purchase_time) AS "month", COUNT(*)::bigint n
 FROM semantic.order_item_product_evidence_v1
 GROUP BY 1
)
SELECT json_build_object('raw', (SELECT row_to_json(raw) FROM raw), 'derived',(SELECT row_to_json(derived) FROM derived),
 'months',(SELECT COUNT(*) FROM monthly),'approved_for_mcp',false,'inventory_claim_allowed',false)::text;

