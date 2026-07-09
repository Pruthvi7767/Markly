"""SQLAlchemy engine + session factory.

Reads DATABASE_URL from environment. Fails loudly if not set —
per AGENTS.md: nothing fails silently.
"""
import os
import logging
from sqlalchemy import create_engine, event
from sqlalchemy.engine import Engine

logger = logging.getLogger(__name__)
_engine: Engine | None = None


def get_engine() -> Engine:
    """Return a cached SQLAlchemy engine. Raises on missing DATABASE_URL."""
    global _engine
    if _engine is not None:
        return _engine

    db_url = os.environ.get("DATABASE_URL")
    if not db_url:
        raise RuntimeError(
            "DATABASE_URL is not set. "
            "Copy .env.example to .env and fill in your Postgres connection string."
        )

    _engine = create_engine(
        db_url,
        pool_pre_ping=True,   # detect stale connections
        pool_size=2,
        max_overflow=3,
    )
    logger.info("DB engine created: %s", db_url.split("@")[-1])  # log host only, not credentials
    return _engine
