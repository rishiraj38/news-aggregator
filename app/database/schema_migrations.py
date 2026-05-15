"""Lightweight additive schema updates (no Alembic). Safe to run on startup."""

from sqlalchemy import inspect, text

from app.database.connection import engine


def _add_column_if_missing(table: str, column: str, sql_type: str) -> None:
    insp = inspect(engine)
    if table not in insp.get_table_names():
        return
    existing = {c["name"] for c in insp.get_columns(table)}
    if column in existing:
        return
    with engine.begin() as conn:
        conn.execute(text(f"ALTER TABLE {table} ADD COLUMN {column} {sql_type}"))


def ensure_image_url_columns() -> None:
    """Add image_url to article and digest tables when missing."""
    if engine.dialect.name == "sqlite":
        col_type = "TEXT"
    else:
        col_type = "VARCHAR"
    for table in (
        "digests",
        "youtube_videos",
        "openai_articles",
        "anthropic_articles",
        "general_rss_articles",
    ):
        _add_column_if_missing(table, "image_url", col_type)
