"""Database connectivity.

Marked as integration: it needs a live PostgreSQL instance and is skipped when
DATABASE_URL is not configured, so a fresh clone can still run `make test`.
"""

import os

import pytest
from sqlalchemy import text

from database import check_connection, get_engine, session_scope

pytestmark = pytest.mark.skipif(
    not os.getenv("DATABASE_URL"),
    reason="DATABASE_URL is not set; see .env.example",
)


@pytest.mark.integration
def test_check_connection_succeeds() -> None:
    check_connection()


@pytest.mark.integration
def test_session_scope_yields_a_working_session() -> None:
    with session_scope() as session:
        assert session.execute(text("SELECT 1")).scalar_one() == 1


@pytest.mark.integration
def test_server_is_postgresql() -> None:
    with get_engine().connect() as connection:
        version = connection.execute(text("SELECT version()")).scalar_one()
    assert "PostgreSQL" in version
