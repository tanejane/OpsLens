-- OPTIONAL MANUAL APPROVAL, NOT AUTOMATICALLY APPLIED.
-- Only run after validating policy, period coverage, and isolated role behavior.
-- This does not alter any application's MCP SQL allowlist.
BEGIN;
GRANT USAGE ON SCHEMA semantic TO opslens_mcp_reader;
GRANT SELECT ON semantic.order_review_evidence_v1 TO opslens_mcp_reader;
COMMIT;
