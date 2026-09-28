"""
Database URL normalisation.

SQLAlchemy 2.1 changed the default PostgreSQL DBAPI from psycopg2 to psycopg
(v3). With `requirements.txt` unbounded, CI picked 2.1 up on 2026-09-25 and
both crons died at import — `ModuleNotFoundError: No module named 'psycopg'` —
while local machines on 2.0 kept working. The URL now names the driver.
"""

import importlib

import pytest

from app.database.connection import normalize_database_url


@pytest.mark.parametrize(
    "given, expected",
    [
        ("postgresql://u:p@host/db", "postgresql+psycopg2://u:p@host/db"),
        ("postgres://u:p@host/db", "postgresql+psycopg2://u:p@host/db"),
        ("postgresql+psycopg2://u:p@host/db", "postgresql+psycopg2://u:p@host/db"),
    ],
)
def test_postgres_urls_name_the_installed_driver(given, expected):
    assert normalize_database_url(given) == expected


@pytest.mark.parametrize(
    "url",
    [
        "postgresql+psycopg://u:p@host/db",  # someone deliberately choosing v3
        "postgresql+asyncpg://u:p@host/db",
        "sqlite:///./local.db",
        "sqlite+pysqlite:///:memory:",
    ],
)
def test_explicit_drivers_and_sqlite_are_left_alone(url):
    assert normalize_database_url(url) == url


def test_query_string_and_credentials_survive():
    given = "postgresql://user:p%40ss-w0rd@ep-cool.neon.tech/neondb?sslmode=require&channel_binding=require"
    out = normalize_database_url(given)
    assert out.startswith("postgresql+psycopg2://user:p%40ss-w0rd@ep-cool.neon.tech/")
    assert out.endswith("?sslmode=require&channel_binding=require")


def test_engine_is_built_with_psycopg2(monkeypatch):
    """The failure was at import time, when create_engine() resolves the DBAPI."""
    monkeypatch.setenv("DATABASE_URL", "postgresql://u:p@host/db")
    connection = importlib.reload(importlib.import_module("app.database.connection"))
    try:
        assert connection.engine.dialect.driver == "psycopg2"
    finally:
        monkeypatch.delenv("DATABASE_URL", raising=False)
        importlib.reload(connection)
