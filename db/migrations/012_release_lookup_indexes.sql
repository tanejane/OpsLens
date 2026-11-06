-- Index underlying join keys, preserving duplicate rows for the grain audit.
CREATE INDEX IF NOT EXISTS release_orders_id ON staging.olist_orders (order_id);
CREATE INDEX IF NOT EXISTS release_items_order ON staging.olist_order_items (order_id);
CREATE INDEX IF NOT EXISTS release_reviews_order ON staging.olist_order_reviews (order_id);
CREATE INDEX IF NOT EXISTS release_finance_order ON staging.order_profitability (order_id);
CREATE INDEX IF NOT EXISTS release_capacity_order ON staging.regional_capacity_overrides (order_id);
CREATE INDEX IF NOT EXISTS release_campaign_order ON staging.inc006_effective_marketing_economics (order_id);
CREATE INDEX IF NOT EXISTS release_delivery_order ON staging.effective_delivery_dates (order_id);
CREATE INDEX IF NOT EXISTS release_cx_order ON staging.cx_incident_overrides (order_id);
CREATE INDEX IF NOT EXISTS release_returns_order ON staging.returns (order_id);
ANALYZE staging.olist_orders, staging.olist_order_items, staging.olist_order_reviews,
    staging.order_profitability, staging.regional_capacity_overrides, staging.inc006_effective_marketing_economics,
    staging.effective_delivery_dates, staging.cx_incident_overrides, staging.returns;
