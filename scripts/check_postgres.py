from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv
from sqlalchemy import create_engine, text

ROOT = Path(__file__).resolve().parents[1]
load_dotenv(ROOT / ".env")

url = os.getenv(
    "DATABASE_URL",
    "postgresql+psycopg://opslens_admin:opslens_local_dev@localhost:5432/opslens",
)

engine = create_engine(url, pool_pre_ping=True)

expected_schemas = {
    "staging", "commerce", "catalog", "operations", "finance",
    "marketing", "inventory", "cx", "behavior", "knowledge",
    "semantic", "observability",
}

with engine.connect() as conn:
    version = conn.execute(text("SELECT version()")).scalar_one()
    extensions = {
        r[0]
        for r in conn.execute(
            text(
                "SELECT extname FROM pg_extension "
                "WHERE extname IN ('vector', 'pg_trgm', 'pgcrypto')"
            )
        )
    }
    schemas = {
        r[0]
        for r in conn.execute(
            text("SELECT schema_name FROM information_schema.schemata")
        )
    }
    role_exists = conn.execute(
        text(
            "SELECT EXISTS (SELECT 1 FROM pg_roles "
            "WHERE rolname = 'opslens_agent_reader')"
        )
    ).scalar_one()

print("=" * 78)
print("OPSLENS PHASE 2A — POSTGRES FOUNDATION CHECK")
print("=" * 78)
print("Connected:", True)
print("PostgreSQL:", version.split(",")[0])
print("Extensions:", sorted(extensions))
print("Agent reader role exists:", bool(role_exists))

missing_ext = {"vector", "pg_trgm", "pgcrypto"} - extensions
missing_schemas = expected_schemas - schemas

print("Schemas present:", len(expected_schemas - missing_schemas), "/", len(expected_schemas))

if missing_ext:
    print("FAIL missing extensions:", sorted(missing_ext))
if missing_schemas:
    print("FAIL missing schemas:", sorted(missing_schemas))

if missing_ext or missing_schemas or not role_exists:
    raise SystemExit(1)

print("\nPASS: PostgreSQL foundation is ready.")
print("Hidden eval_ground_truth is intentionally not loaded into this database.")
