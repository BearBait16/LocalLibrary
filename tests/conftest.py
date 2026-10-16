import dataclasses

import psycopg
import pytest

from locallibrary import config as config_module
from locallibrary import db

TEST_DB = "locallibrary_test"


@pytest.fixture
def test_db(monkeypatch):
    """Point db.py at a separate database on the same server, with empty tables."""
    base = config_module.config.database_url
    test_url = base.rsplit("/", 1)[0] + f"/{TEST_DB}"
    try:
        with psycopg.connect(base, autocommit=True, connect_timeout=3) as conn:
            if not conn.execute("SELECT 1 FROM pg_database WHERE datname = %s", (TEST_DB,)).fetchone():
                conn.execute(f"CREATE DATABASE {TEST_DB}")
    except psycopg.OperationalError:
        pytest.skip("Postgres is not running (docker compose up -d)")
    monkeypatch.setattr(db, "config", dataclasses.replace(config_module.config, database_url=test_url))
    db.init_schema()
    with db.connect() as conn:
        conn.execute("TRUNCATE shelf_book_sources, shelf_books, chunks, sources RESTART IDENTITY CASCADE")
    return db
