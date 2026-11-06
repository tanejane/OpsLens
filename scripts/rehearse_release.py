"""Provision an isolated database, run release checks, then discard only that container."""
import argparse
import os
from pathlib import Path
import secrets
import subprocess
import sys
import time
import uuid
from psycopg import sql

ROOT = Path(__file__).resolve().parents[1]


def copy_batch(table, conn, keys, rows):
    statement = sql.SQL("COPY {}.{} ({}) FROM STDIN").format(
        sql.Identifier(table.schema), sql.Identifier(table.name),
        sql.SQL(", ").join(map(sql.Identifier, keys)))
    with conn.connection.driver_connection.cursor() as cursor, cursor.copy(statement) as stream:
        for row in rows:
            stream.write_row(row)


def initialize(expected_database):
    from scripts import load_phase2b_v3 as loader
    from scripts import setup_phase2d_runtime_role as roles

    # This internal step must never replace staging tables on an installed system.
    with loader.engine.connect() as conn:
        database, occupied = conn.exec_driver_sql("""
            SELECT current_database(), EXISTS (SELECT FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace
                WHERE n.nspname !~ '^pg_' AND n.nspname <> 'information_schema'
                AND c.relkind IN ('r','f','p','v','m','S'))
        """).one()
    if not expected_database or database != expected_database or occupied:
        raise RuntimeError("Expected an explicitly named, empty database")
    _, _, _, docs, sources = loader.paths_for(ROOT)
    loader.assert_runtime_manifest_safe(sources)
    for path in sources.values():
        if not path.is_file():
            raise FileNotFoundError(path.name)
    with loader.engine.begin() as conn:
        for filename in ("db/init/001_extensions.sql","db/init/002_schemas.sql"):
            conn.exec_driver_sql((ROOT / filename).read_text(encoding="utf-8-sig"))
    for name, path in sources.items():
        loader.load_csv(name, path, method=copy_batch)
    loader.load_documents(ROOT, docs)
    loader.require_staging_tables()
    loader.create_canonical_views()
    roles.main()
    with loader.engine.connect().execution_options(isolation_level="AUTOCOMMIT") as conn:
        for filename in ("db/migrations/011_phase4c4_cost_components.sql","db/migrations/012_release_lookup_indexes.sql", "sql/phase4c10_review_view.sql",
                         "sql/phase4c14_delivery_view.sql", "sql/phase4c19_item_evidence.sql"):
            conn.exec_driver_sql((ROOT / filename).read_text(encoding="utf-8-sig"))
    from scripts.build_phase3d_index import main as index_documents
    index_documents()
    roles.main()


def rehearse(command):
    name = "opslens-release-" + uuid.uuid4().hex[:12]
    database = name.replace("opslens-release-", "release_")
    admin_password, reader_password = secrets.token_urlsafe(24), secrets.token_urlsafe(24)
    env = dict(os.environ, POSTGRES_DB=database, POSTGRES_USER="release_admin", POSTGRES_PASSWORD=admin_password)
    def docker(*args):
        return subprocess.check_output(["docker", *args], env=env, text=True).strip()
    container = docker("run", "--detach", "--rm", "--name", name, "-e", "POSTGRES_DB", "-e", "POSTGRES_USER",
                       "-e", "POSTGRES_PASSWORD", "-p", "127.0.0.1::5432", "-v",
                       f"{ROOT / 'db/init'}:/docker-entrypoint-initdb.d:ro", "pgvector/pgvector:0.8.2-pg16")
    try:
        port = docker("port", container, "5432/tcp").rsplit(":", 1)[1]
        for _ in range(90):
            probe = subprocess.run(["docker","exec",container,"pg_isready","-h","127.0.0.1","-U","release_admin","-d",database],
                                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            if probe.returncode == 0:
                break
            time.sleep(1)
        else:
            raise RuntimeError("Disposable PostgreSQL did not start")
        env.update(OPSLENS_DISPOSABLE_DB=database, MCP_DB_USER="opslens_mcp_reader", MCP_DB_PASSWORD=reader_password,
                   DATABASE_URL=f"postgresql+psycopg://release_admin:{admin_password}@127.0.0.1:{port}/{database}",
                   MCP_DATABASE_URL=f"postgresql+psycopg://opslens_mcp_reader:{reader_password}@127.0.0.1:{port}/{database}")
        subprocess.run([sys.executable, "-m", "scripts.rehearse_release", "--provision-empty", database],
                       env=env, cwd=ROOT, check=True)
        subprocess.run(command or [sys.executable, "-m", "scripts.release_checks"], env=env, cwd=ROOT, check=True)
    finally:
        docker("stop", container)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--provision-empty", metavar="DATABASE", help="Provision an explicitly named empty dedicated database and retain it")
    parser.add_argument("command", nargs=argparse.REMAINDER)
    args = parser.parse_args()
    if args.provision_empty:
        initialize(args.provision_empty)
    else:
        rehearse(args.command)
