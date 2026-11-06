SELECT json_build_object(
 'view_exists', to_regclass('semantic.order_delivery_evidence_v1') IS NOT NULL,
 'reader_exists', EXISTS(SELECT 1 FROM pg_roles WHERE rolname='opslens_mcp_reader'),
 'reader_schema_usage', has_schema_privilege('opslens_mcp_reader','semantic','USAGE'),
 'reader_select', has_table_privilege('opslens_mcp_reader','semantic.order_delivery_evidence_v1','SELECT'));
