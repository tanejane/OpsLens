-- Phase 4C.21 corrected read-only census. No FULL JOIN on nullable category keys.
-- UNION ALL + GROUP BY retains one NULL bucket and categories present on only one side.
WITH source_categories AS (
 SELECT p.product_category_name AS raw_category, count(*)::bigint AS products,
        0::bigint AS item_units, 0::bigint AS distinct_orders, 0::numeric AS item_gmv
 FROM catalog.products p GROUP BY p.product_category_name
), item_categories AS (
 SELECT p.product_category_name AS raw_category, 0::bigint AS products,
        count(*)::bigint AS item_units,
        count(DISTINCT i.order_id)::bigint AS distinct_orders,
        coalesce(sum(i.price),0)::numeric AS item_gmv
 FROM commerce.order_items i LEFT JOIN catalog.products p ON p.product_id=i.product_id
 GROUP BY p.product_category_name
), combined AS (
 SELECT * FROM source_categories
 UNION ALL
 SELECT * FROM item_categories
), category_census AS (
 SELECT raw_category, sum(products)::bigint AS products,
        sum(item_units)::bigint AS item_units,
        sum(distinct_orders)::bigint AS distinct_orders,
        sum(item_gmv)::numeric(20,2) AS item_gmv
 FROM combined GROUP BY raw_category
)
SELECT json_build_object(
 'contract','opslens_product_categories_census_v1',
 'categories', (SELECT coalesce(json_agg(json_build_object('raw_category',raw_category,'products',products,'item_units',item_units,'distinct_orders',distinct_orders,'item_gmv',item_gmv) ORDER BY raw_category NULLS FIRST),'[]'::json) FROM category_census),
 'source_product_count',(SELECT count(*) FROM catalog.products),
 'source_item_count',(SELECT count(*) FROM commerce.order_items),
 'source_item_gmv',(SELECT coalesce(sum(price),0)::numeric(20,2) FROM commerce.order_items)
)::text;
