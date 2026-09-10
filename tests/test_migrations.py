"""Additive schema migrations run on every startup, so they must be idempotent
and must never break rows that predate them."""

import importlib

import pytest
from sqlalchemy import inspect, text


@pytest.fixture()
def legacy_db(tmp_path, monkeypatch):
    """A users table as it existed before `plan` and `pro_requested_at`."""
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{tmp_path}/legacy.db")
    from app.database import connection as conn_mod

    importlib.reload(conn_mod)
    import app.database.schema_migrations as mig

    importlib.reload(mig)

    with conn_mod.engine.begin() as conn:
        conn.execute(text("CREATE TABLE users (id VARCHAR PRIMARY KEY, email VARCHAR, role VARCHAR)"))
        conn.execute(text("INSERT INTO users (id, email, role) VALUES ('u1', 'a@example.com', 'user')"))
    return conn_mod.engine, mig


def _columns(engine):
    return {c["name"] for c in inspect(engine).get_columns("users")}


def test_plan_column_backfills_existing_rows_to_free(legacy_db):
    engine, mig = legacy_db
    mig.ensure_plan_column()
    with engine.connect() as conn:
        assert conn.execute(text("SELECT plan FROM users WHERE id = 'u1'")).scalar() == "free"


def test_pro_request_column_is_null_for_existing_rows(legacy_db):
    """NULL means "no pending request" — nobody should appear to have asked."""
    engine, mig = legacy_db
    mig.ensure_pro_request_column()
    assert "pro_requested_at" in _columns(engine)
    with engine.connect() as conn:
        assert conn.execute(text("SELECT pro_requested_at FROM users WHERE id = 'u1'")).scalar() is None


def test_migrations_are_idempotent(legacy_db):
    engine, mig = legacy_db
    for _ in range(3):
        mig.ensure_plan_column()
        mig.ensure_pro_request_column()
    assert {"plan", "pro_requested_at"} <= _columns(engine)
