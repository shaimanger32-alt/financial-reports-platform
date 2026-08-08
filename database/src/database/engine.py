"""Engine and session management.

Synchronous SQLAlchemy is used deliberately: the workload is batch ingestion plus
reads of precomputed snapshots (spec sections 23, 37), neither of which benefits
from async. FastAPI runs synchronous endpoints in a threadpool.
"""

from collections.abc import Iterator
from contextlib import contextmanager
from functools import lru_cache

from sqlalchemy import Engine, create_engine, text
from sqlalchemy.orm import Session, sessionmaker

from database.config import get_database_settings


@lru_cache(maxsize=1)
def get_engine() -> Engine:
    """Return the process-wide engine."""
    settings = get_database_settings()
    return create_engine(
        settings.database_url,
        echo=settings.sql_echo,
        pool_pre_ping=True,
        future=True,
    )


@lru_cache(maxsize=1)
def _get_session_factory() -> sessionmaker[Session]:
    return sessionmaker(bind=get_engine(), expire_on_commit=False)


@contextmanager
def session_scope() -> Iterator[Session]:
    """Provide a transactional session, rolling back on error."""
    session = _get_session_factory()()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def check_connection() -> None:
    """Raise if the database is unreachable. Used by the API health check."""
    with get_engine().connect() as connection:
        connection.execute(text("SELECT 1"))
