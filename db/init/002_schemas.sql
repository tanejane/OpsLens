CREATE SCHEMA IF NOT EXISTS staging;
CREATE SCHEMA IF NOT EXISTS commerce;
CREATE SCHEMA IF NOT EXISTS catalog;
CREATE SCHEMA IF NOT EXISTS operations;
CREATE SCHEMA IF NOT EXISTS finance;
CREATE SCHEMA IF NOT EXISTS marketing;
CREATE SCHEMA IF NOT EXISTS inventory;
CREATE SCHEMA IF NOT EXISTS cx;
CREATE SCHEMA IF NOT EXISTS behavior;
CREATE SCHEMA IF NOT EXISTS knowledge;
CREATE SCHEMA IF NOT EXISTS semantic;
CREATE SCHEMA IF NOT EXISTS observability;

COMMENT ON SCHEMA staging IS
'Loaded source and controlled synthetic tables before canonicalization. Not exposed directly to the agent.';
COMMENT ON SCHEMA commerce IS
'Canonical orders, customers, payments, and order-item business entities.';
COMMENT ON SCHEMA catalog IS
'Canonical product and category entities.';
COMMENT ON SCHEMA operations IS
'Canonical seller, delivery, fulfillment, and operational event entities.';
COMMENT ON SCHEMA finance IS
'Canonical profitability, P&L, cost, and refund facts.';
COMMENT ON SCHEMA marketing IS
'Canonical campaigns, attribution, spend, and marketing economics.';
COMMENT ON SCHEMA inventory IS
'Canonical availability, stockout, and inventory facts.';
COMMENT ON SCHEMA cx IS
'Canonical reviews and customer-experience facts.';
COMMENT ON SCHEMA behavior IS
'GA4-derived behavioral sessions and funnel facts.';
COMMENT ON SCHEMA knowledge IS
'Internal documents and retrieval metadata.';
COMMENT ON SCHEMA semantic IS
'Metric definitions and stable business-facing views used by tools.';
COMMENT ON SCHEMA observability IS
'Optional metadata for ingestion/runtime lineage.';

DO $$
BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'opslens_agent_reader') THEN
    CREATE ROLE opslens_agent_reader NOLOGIN;
  END IF;
END $$;

GRANT USAGE ON SCHEMA
  commerce, catalog, operations, finance, marketing,
  inventory, cx, behavior, knowledge, semantic
TO opslens_agent_reader;

-- The dedicated MCP login receives named relation grants after view provisioning.
