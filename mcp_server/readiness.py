"""Read-only release checks using the configured MCP credential."""
import os
from sqlalchemy import text
from mcp_server.policy import RELATIONS
from mcp_server.runtime_tools import engine


def inspect_runtime():
    with engine.begin() as conn:
        conn.exec_driver_sql("SET LOCAL statement_timeout = '3s'")
        role = conn.exec_driver_sql("""
            SELECT current_user AS name, current_setting('server_version_num')::int AS version,
                current_setting('transaction_read_only') = 'on' AS readonly,
                rolsuper OR rolcreatedb OR rolcreaterole OR rolreplication OR rolbypassrls
                    OR EXISTS (SELECT FROM pg_auth_members WHERE member=pg_roles.oid) AS elevated,
                has_schema_privilege(current_user,'staging','USAGE') OR
                    has_schema_privilege(current_user,'observability','USAGE') AS hidden_access,
                has_database_privilege(current_user,current_database(),'CREATE,TEMP') AS db_create,
                has_function_privilege(current_user,'pg_catalog.query_to_xml(text,boolean,boolean,text)','EXECUTE') AS indirect
            FROM pg_roles WHERE rolname=current_user
        """).mappings().one()
        rows = conn.execute(text("""
            SELECT n.nspname || '.' || c.relname AS relation,
                has_table_privilege(c.oid,'SELECT') AS readable,
                has_table_privilege(c.oid,'INSERT,UPDATE,DELETE,TRUNCATE,TRIGGER,REFERENCES') AS writable,
                has_schema_privilege(n.oid,'CREATE') AS schema_create
            FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace
            WHERE c.relkind IN ('r','v','m','p','f') AND has_schema_privilege(n.oid,'USAGE')
                AND n.nspname <> 'information_schema' AND n.nspname !~ '^pg_'
        """)).mappings().all()
        sources = {row["relation"] for row in rows if row["readable"]}
        checks = {
            "postgres_16": 160000 <= role["version"] < 170000,
            "runtime_identity": role["name"] == os.environ.get("MCP_DB_USER", "opslens_mcp_reader"),
            "restricted_role": role["readonly"] and not role["elevated"] and not role["hidden_access"],
            "no_create_or_indirect_sql": not role["db_create"] and not role["indirect"],
            "named_relations_only": sources == RELATIONS,
            "no_relation_writes": not any(row["writable"] or row["schema_create"] for row in rows),
        }
        if "knowledge.document_chunks" in sources:
            checks["indexed_documents"] = conn.exec_driver_sql(
                "SELECT EXISTS (SELECT FROM knowledge.document_chunks WHERE embedding IS NOT NULL)"
            ).scalar_one()
        return {"status": "READY" if all(checks.values()) else "NOT_READY", "checks": checks,
                "missing_sources": sorted(RELATIONS - sources), "unexpected_source_count": len(sources - RELATIONS)}
