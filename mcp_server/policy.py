"""Published PostgreSQL relations and SQLGlot function names used by governed SQL."""
RELATIONS = frozenset("""
behavior.sessions catalog.products commerce.customers commerce.order_items commerce.orders
commerce.payments cx.effective_reviews cx.returns cx.reviews finance.daily_pnl
finance.order_profitability_base finance.order_profitability_effective inventory.effective_sales
inventory.stockout_events inventory.weekly knowledge.document_chunks knowledge.documents
marketing.campaigns marketing.inc006_effective_economics marketing.order_attribution
marketing.spend_daily operations.delivery_effective operations.sellers semantic.daily_commerce
semantic.ga4_funnel_daily semantic.misleading_correlation_fixture semantic.order_cost_components
semantic.order_delivery_evidence_v1 semantic.order_economics semantic.order_item_product_evidence_v1
semantic.order_review_evidence_v1 semantic.product_mix_effective semantic.stockout_effective_sales
""".split())

# SQLGlot models CASE, AND, OR, IF and EXISTS as Func nodes too.
FUNCTIONS = frozenset("""
ABS AND AVG BTRIM CASE CAST COALESCE COUNT CURRENT_DATE DATE DATE_TRUNC EXISTS EXTRACT
GREATEST IF JSONB_AGG TO_JSONB LEAST LOGICAL_OR LOWER MAX MIN NULLIF OR ROUND ROW_NUMBER SUM TIMESTAMP_TRUNC
TRIM UPPER
""".split())
CAST_TYPES = frozenset("BOOLEAN SMALLINT INT BIGINT DECIMAL FLOAT DOUBLE DATE TIMESTAMP TIMESTAMPTZ TEXT VARCHAR INTERVAL JSONB".split())
