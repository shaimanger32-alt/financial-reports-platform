"""PostgreSQL persistence layer.

Owned separately from the API so that the ingestion pipeline can reach the
database without depending on the web service (spec section 8: ingestion and
API are peers over one canonical store).

The financial schema itself is intentionally NOT defined yet. Per spec section 52
(Task D) the canonical model is designed only after the real MAGNA payload has
been inspected in phase 1.
"""

from database.config import DatabaseSettings, get_database_settings
from database.engine import check_connection, get_engine, session_scope

__all__ = [
    "DatabaseSettings",
    "check_connection",
    "get_database_settings",
    "get_engine",
    "session_scope",
]
