-- Phase 4C.19: item-grain product evidence; does not grant MCP permissions.
BEGIN;
CREATE OR REPLACE VIEW semantic.order_item_product_evidence_v1 AS
SELECT i.order_id, i.order_item_id, i.product_id, i.seller_id,
       o.order_purchase_timestamp::timestamp AS order_purchase_time,
       COALESCE(NULLIF(btrim(p.product_category_name), ''), 'Unknown')::text AS category,
       i.price::numeric AS item_price,
       i.freight_value::numeric AS freight_value
FROM commerce.order_items i
JOIN commerce.orders o ON o.order_id=i.order_id
LEFT JOIN catalog.products p ON p.product_id=i.product_id;
COMMENT ON VIEW semantic.order_item_product_evidence_v1 IS '4C19 item-grain sales evidence; Unknown category retained; no inventory claims or category profit attribution.';
COMMIT;
