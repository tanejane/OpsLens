-- Read-only diagnostics. Run with admin user, not MCP reader.
SELECT json_build_object(
 'view_exists', to_regclass('semantic.order_review_evidence_v1') IS NOT NULL,
 'mcp_reader_exists', EXISTS (SELECT 1 FROM pg_roles WHERE rolname='opslens_mcp_reader'),
 'mcp_has_schema_usage', has_schema_privilege('opslens_mcp_reader','semantic','USAGE'),
 'mcp_can_select_review_view', has_table_privilege('opslens_mcp_reader','semantic.order_review_evidence_v1','SELECT')
)::text;
