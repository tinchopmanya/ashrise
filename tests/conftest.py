import os
from pathlib import Path

import psycopg
from psycopg import sql
from psycopg.rows import dict_row
import pytest
from fastapi.testclient import TestClient


REPO_ROOT = Path("/workspace") if Path("/workspace/sql/001_init.sql").exists() else Path(__file__).resolve().parents[1]
SEED_SQL = (REPO_ROOT / "sql" / "001_init.sql").read_text(encoding="utf-8")
TEST_DB_NAME = os.getenv("TEST_DATABASE_NAME", "ashrise_test")
ADMIN_DATABASE_URL = os.getenv("TEST_ADMIN_DATABASE_URL", "postgresql://postgres:postgres@db:5432/postgres")
TEST_DATABASE_URL = os.getenv("TEST_DATABASE_URL", f"postgresql://postgres:postgres@db:5432/{TEST_DB_NAME}")
TEST_TOKEN = "test-token"


def recreate_test_database():
    with psycopg.connect(ADMIN_DATABASE_URL, autocommit=True) as conn:
        conn.execute(
            "SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname = %s AND pid <> pg_backend_pid()",
            (TEST_DB_NAME,),
        )
        conn.execute(sql.SQL("DROP DATABASE IF EXISTS {}").format(sql.Identifier(TEST_DB_NAME)))
        conn.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(TEST_DB_NAME)))

    with psycopg.connect(TEST_DATABASE_URL, autocommit=True) as conn:
        conn.execute(SEED_SQL)


@pytest.fixture(scope="session")
def app_client():
    recreate_test_database()
    os.environ["DATABASE_URL"] = TEST_DATABASE_URL
    os.environ["ASHRISE_TOKEN"] = TEST_TOKEN

    from app.config import get_settings
    from app.main import create_app

    get_settings.cache_clear()

    with TestClient(create_app()) as client:
        yield client


@pytest.fixture
def auth_headers():
    return {"Authorization": f"Bearer {TEST_TOKEN}"}


@pytest.fixture
def db_conn():
    with psycopg.connect(TEST_DATABASE_URL, autocommit=True, row_factory=dict_row) as conn:
        yield conn
