-- Phase 4C.4: additive semantic exposure of existing modeled finance components.
-- Apply with a privileged migration account; runtime only receives SELECT.
-- The finance view already defines the authoritative effective profit accounting.
CREATE OR REPLACE VIEW semantic.order_cost_components AS
SELECT
  order_id,
  order_purchase_timestamp,
  effective_revenue,
  effective_cogs,
  effective_contribution_profit,
  COALESCE(refund_amount, 0)::double precision AS refund_amount,
  COALESCE(fulfillment_cost, 0)::double precision AS fulfillment_cost,
  COALESCE(payment_processing_cost, 0)::double precision AS payment_processing_cost,
  (COALESCE(marketing_cost, 0) + COALESCE(inc006_marketing_cost, 0))::double precision AS marketing_cost_effective,
  (COALESCE(campaign_incentive_cost, 0) + COALESCE(inc006_incentive_cost, 0))::double precision AS incentive_cost_effective,
  -- Preserve explicit accounting identity, even for adjusted or synthetic rows.
  (COALESCE(effective_revenue,0) - COALESCE(effective_cogs,0) - COALESCE(effective_contribution_profit,0)
  - COALESCE(refund_amount,0) - COALESCE(fulfillment_cost,0)
  - COALESCE(payment_processing_cost,0) - COALESCE(marketing_cost,0)
  - COALESCE(inc006_marketing_cost,0) - COALESCE(campaign_incentive_cost,0)
  - COALESCE(inc006_incentive_cost,0))::double precision AS other_adjustments_residual
FROM finance.order_profitability_effective;

-- Grant explicitly to the existing read-only runtime role; no write permission.
GRANT USAGE ON SCHEMA semantic TO opslens_mcp_reader;
GRANT SELECT ON semantic.order_cost_components TO opslens_mcp_reader;
COMMENT ON VIEW semantic.order_cost_components IS 'Modeled finance components, descriptive only; residual includes unclassified adjustments';
