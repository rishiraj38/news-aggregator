"""Lightweight additive schema updates (no Alembic). Safe to run on startup."""

import logging

from sqlalchemy import inspect, text

from app.database.connection import engine

_logger = logging.getLogger(__name__)


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


def ensure_plan_column() -> None:
    """Add users.plan ("free" | "pro").

    Existing rows are backfilled to "free" by the column default. Admins are
    unaffected, because role="admin" overrides plan everywhere it is checked.
    """
    col_type = "TEXT DEFAULT 'free'" if engine.dialect.name == "sqlite" else "VARCHAR DEFAULT 'free'"
    _add_column_if_missing("users", "plan", col_type)


def ensure_pro_request_column() -> None:
    """Add users.pro_requested_at.

    Set when a Free subscriber requests Pro from the dashboard, and cleared when
    an admin approves or declines it. Stands in for a checkout until payments
    exist. Existing rows are NULL, meaning "no pending request".
    """
    _add_column_if_missing("users", "pro_requested_at", "TIMESTAMP")


def ensure_instagram_posted_column() -> None:
    """Add posted_to_instagram to digests table (tracks which stories were already posted)."""
    col_type = "TEXT" if engine.dialect.name == "sqlite" else "VARCHAR"
    _add_column_if_missing("digests", "posted_to_instagram", col_type)


# (index name, table, columns) — additive and idempotent via IF NOT EXISTS.
_INDEXES: tuple[tuple[str, str, str], ...] = (
    # Anti-join in get_articles_without_digest: "does a digest already exist for
    # this article?". Without it every candidate row triggers a sequential scan
    # of the digests table, which grows by ~430 rows a day.
    ("ix_digests_type_article", "digests", "article_type, article_id"),
    # Per-source newest-first candidate lookup.
    ("ix_general_rss_source_pub", "general_rss_articles", "source, published_at"),
    # Recent-digest window used by personalization and Instagram publishing.
    ("ix_digests_created_at", "digests", "created_at"),
    # Per-user "already recommended" lookup during personalization.
    ("ix_recommendations_user", "recommendations", "user_id"),
    # Admin console: deliveries by day, and one subscriber's send history.
    ("ix_email_deliveries_sent_at", "email_deliveries", "sent_at"),
    ("ix_email_deliveries_user", "email_deliveries", "user_id"),
)


def ensure_lookup_indexes() -> None:
    """Create the indexes the daily pipeline depends on, if they are missing.

    Both PostgreSQL and SQLite support CREATE INDEX IF NOT EXISTS, so this is
    safe to run on every startup.
    """
    insp = inspect(engine)
    tables = set(insp.get_table_names())
    for name, table, columns in _INDEXES:
        if table not in tables:
            continue
        try:
            with engine.begin() as conn:
                conn.execute(
                    text(f"CREATE INDEX IF NOT EXISTS {name} ON {table} ({columns})")
                )
        except Exception as exc:  # noqa: BLE001
            # An index is an optimisation, never a correctness requirement.
            _logger.warning("Could not create index %s on %s: %s", name, table, exc)
