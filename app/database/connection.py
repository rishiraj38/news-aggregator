import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from dotenv import load_dotenv

load_dotenv()


def get_environment() -> str:
    return os.getenv("ENVIRONMENT", "LOCAL").upper()


# The DBAPI this project actually installs (see requirements.txt).
_PG_DRIVER = "psycopg2"


def normalize_database_url(url: str) -> str:
    """
    Name the PostgreSQL driver in the URL instead of relying on SQLAlchemy's default.

    SQLAlchemy 2.1 changed that default from psycopg2 to psycopg (v3). A bare
    `postgresql://` URL then tries to import a package this project doesn't
    install, and every cron run died at import with:

        ModuleNotFoundError: No module named 'psycopg'

    Also normalises the `postgres://` scheme that Neon and Heroku hand out.
    URLs that already name a driver (`+psycopg`, `+asyncpg`, …) are left alone,
    as is anything that isn't PostgreSQL — SQLite, used by the tests.
    """
    if url.startswith("postgres://"):
        url = "postgresql://" + url[len("postgres://") :]
    if url.startswith("postgresql://"):
        url = f"postgresql+{_PG_DRIVER}://" + url[len("postgresql://") :]
    return url


def get_database_url() -> str:
    database_url = os.getenv("DATABASE_URL")
    if database_url:
        return normalize_database_url(database_url)

    user = os.getenv("POSTGRES_USER", "postgres")
    password = os.getenv("POSTGRES_PASSWORD", "postgres")
    host = os.getenv("POSTGRES_HOST", "localhost")
    port = os.getenv("POSTGRES_PORT", "5432")
    db = os.getenv("POSTGRES_DB", "ai_news_aggregator")
    return normalize_database_url(f"postgresql://{user}:{password}@{host}:{port}/{db}")


def get_database_info() -> dict:
    url = get_database_url()
    env = get_environment()

    if (
        "render.com" in url.lower()
        or "amazonaws.com" in url.lower()
        or env == "PRODUCTION"
    ):
        env_type = "PRODUCTION"
    else:
        env_type = "LOCAL"

    masked_url = url
    if "@" in url:
        parts = url.split("@")
        if len(parts) == 2:
            masked_url = f"{parts[0].split('://')[0]}://***@{parts[1]}"

    return {
        "environment": env_type,
        "url_masked": masked_url,
        "host": url.split("@")[-1].split("/")[0] if "@" in url else "localhost",
    }


engine = create_engine(
    get_database_url(),
    pool_pre_ping=True,       # Detect stale/dead SSL connections before use
    pool_recycle=300,          # Recycle connections every 5 minutes
    pool_size=5,
    max_overflow=10,
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def get_session():
    return SessionLocal()
