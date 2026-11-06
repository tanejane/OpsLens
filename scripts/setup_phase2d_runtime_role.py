
from __future__ import annotations

import os
from pathlib import Path

import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from mcp_server.policy import RELATIONS
from dotenv import load_dotenv
from sqlalchemy import create_engine, text


ROOT = Path(__file__).resolve().parents[1]
load_dotenv(ROOT / ".env")

ADMIN_DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql+psycopg://opslens_admin:opslens_local_dev@localhost:5432/opslens",
)

MCP_DB_USER = os.getenv("MCP_DB_USER", "opslens_mcp_reader")
MCP_DB_PASSWORD = os.getenv("MCP_DB_PASSWORD", "opslens_mcp_local_dev")

ALLOWED_SCHEMAS = [
    "commerce",
    "catalog",
    "operations",
    "finance",
    "marketing",
    "inventory",
    "cx",
    "behavior",
    "knowledge",
    "semantic",
]


def quote_ident(value: str) -> str:
    if not value.replace("_", "").isalnum():
        raise ValueError(f"Unsafe PostgreSQL identifier: {value}")
    return '"' + value.replace('"', '""') + '"'


def quote_literal(value: str) -> str:
    return "'" + value.replace("'", "''") + "'"


def main(*, policy_only=False):
    print("=" * 82)
    print("OPSLENS PHASE 2D — CREATE DEDICATED MCP DATABASE ROLE")
    print("=" * 82)

    engine = create_engine(ADMIN_DATABASE_URL, pool_pre_ping=True)

    role = quote_ident(MCP_DB_USER)
    password = quote_literal(MCP_DB_PASSWORD)

    schemas_csv = ", ".join(quote_ident(s) for s in ALLOWED_SCHEMAS)

    with engine.begin() as conn:
        exists = conn.execute(
            text(
                """
                SELECT EXISTS (
                    SELECT 1
                    FROM pg_roles
                    WHERE rolname = :role_name
                )
                """
            ),
            {"role_name": MCP_DB_USER},
        ).scalar_one()

        database, admin = conn.exec_driver_sql("SELECT current_database(), current_user").one()
        if MCP_DB_USER == admin or MCP_DB_USER.startswith("pg_"):
            raise ValueError("Runtime role must be separate from the provisioning account")
        if exists and conn.execute(text("""SELECT rolsuper OR rolcreaterole OR rolcreatedb
                OR rolreplication OR rolbypassrls OR EXISTS
                (SELECT 1 FROM pg_auth_members WHERE member=pg_roles.oid)
                FROM pg_roles WHERE rolname=:name"""), {"name": MCP_DB_USER}).scalar_one():
            raise ValueError("Refusing to repurpose a privileged role or role member")
        if policy_only and not exists:
            raise ValueError("Existing runtime login required for policy-only migration")
        if not exists:
            conn.exec_driver_sql(
                f"CREATE ROLE {role} LOGIN PASSWORD {password}"
            )
            print(f"[CREATE] role {MCP_DB_USER}")
        elif not policy_only:
            conn.exec_driver_sql(
                f"ALTER ROLE {role} WITH LOGIN PASSWORD {password}"
            )
            print(f"[UPDATE] role {MCP_DB_USER}")

        # Connection only to this database.
        conn.exec_driver_sql(
            f"GRANT CONNECT ON DATABASE {quote_ident(database)} TO {role}"
        )

        # Canonical/semantic runtime schemas only.
        conn.exec_driver_sql(
            f"GRANT USAGE ON SCHEMA {schemas_csv} TO {role}"
        )

        conn.exec_driver_sql(f"REVOKE ALL ON ALL TABLES IN SCHEMA {schemas_csv} FROM {role}")
        for schema in ALLOWED_SCHEMAS:
            conn.exec_driver_sql(
                f"ALTER DEFAULT PRIVILEGES IN SCHEMA {quote_ident(schema)} REVOKE SELECT ON TABLES FROM {role}"
            )
        for relation in sorted(RELATIONS):
            if conn.execute(text("SELECT to_regclass(:relation)"), {"relation": relation}).scalar_one():
                conn.exec_driver_sql(f"GRANT SELECT ON {relation} TO {role}")

        # TEMP and built-in function execution can be inherited from PUBLIC.
        # This provisioning entry point targets a dedicated OpsLens database.
        conn.exec_driver_sql(f"REVOKE TEMPORARY ON DATABASE {quote_ident(database)} FROM PUBLIC, {role}")
        forbidden = conn.exec_driver_sql("""
            SELECT p.oid::regprocedure::text FROM pg_proc p
            WHERE pronamespace='pg_catalog'::regnamespace AND (
                proname ~ '^(query|cursor|table|schema|database)_to_xml'
                OR proname IN ('pg_read_file','pg_read_binary_file','pg_ls_dir',
                               'lo_import','lo_export','pg_logical_emit_message'))
        """).scalars().all()
        for signature in forbidden:
            conn.exec_driver_sql(f"REVOKE EXECUTE ON FUNCTION {signature} FROM PUBLIC, {role}")
        # Defense in depth.
        conn.exec_driver_sql(
            f"REVOKE ALL ON SCHEMA staging FROM {role}"
        )
        conn.exec_driver_sql(
            f"REVOKE ALL ON SCHEMA observability FROM {role}"
        )

        # Runtime session is read-only by default.
        conn.exec_driver_sql(
            f"ALTER ROLE {role} SET default_transaction_read_only = on"
        )
        conn.exec_driver_sql(
            f"ALTER ROLE {role} SET statement_timeout = '5s'"
        )

    print("\nPASS: dedicated MCP runtime role configured.")
    print("\nAdd/update these values in your .env:")
    print(f"MCP_DB_USER={MCP_DB_USER}")
    print("MCP_DB_PASSWORD=<your chosen local password>")
    print(
        "MCP_DATABASE_URL="
        f"postgresql+psycopg://{MCP_DB_USER}:"
        "<password>@localhost:5432/opslens"
    )


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--policy-only", action="store_true", help="Preserve the existing login and password")
    main(policy_only=parser.parse_args().policy_only)
