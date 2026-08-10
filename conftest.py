"""Shared database fixtures, available to every package's tests.

The schema under test is built by running the real migrations, not by
`create_all`. A migration that cannot produce the schema is a migration that
will fail in production, and that is worth catching here.
"""

import os
from collections.abc import Iterator
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import Engine, create_engine, text
from sqlalchemy.orm import Session

REPO_ROOT = Path(__file__).resolve().parent
ALEMBIC_INI = REPO_ROOT / "database" / "alembic.ini"


def _test_database_url() -> str:
    url = os.getenv("TEST_DATABASE_URL")
    if not url:
        pytest.skip("TEST_DATABASE_URL is not set; see .env.example")
    return url


@pytest.fixture(scope="session")
def migrated_engine() -> Iterator[Engine]:
    """An engine pointed at a freshly migrated test database.

    The schema is dropped first rather than downgraded, so a database left
    stamped with a revision that no longer exists cannot wedge the suite.

    The cycle then runs upgrade, downgrade and upgrade again. That is deliberate:
    a downgrade path nobody exercises is a downgrade path that does not work, and
    the first thing it caught was native enum types surviving a table drop.
    """
    url = _test_database_url()

    engine = create_engine(url, future=True)
    with engine.begin() as connection:
        connection.execute(text("DROP SCHEMA public CASCADE"))
        connection.execute(text("CREATE SCHEMA public"))

    config = Config(str(ALEMBIC_INI))
    config.set_main_option("sqlalchemy.url", url)
    command.upgrade(config, "head")
    command.downgrade(config, "base")
    command.upgrade(config, "head")

    try:
        yield engine
    finally:
        engine.dispose()


@pytest.fixture
def session(migrated_engine: Engine) -> Iterator[Session]:
    """A session whose work is rolled back, so tests cannot affect each other."""
    connection = migrated_engine.connect()
    transaction = connection.begin()
    db_session = Session(
        bind=connection, expire_on_commit=False, join_transaction_mode="create_savepoint"
    )
    try:
        yield db_session
    finally:
        db_session.close()
        transaction.rollback()
        connection.close()
