"""PostgreSQL persistence layer.

Owned separately from the API so that the ingestion pipeline can reach the
database without depending on the web service (spec section 8: ingestion and
API are peers over one canonical store).

The canonical schema in `models` was designed after the real MAGNA payload was
inspected in phase 1, as spec section 52 (Task D) requires.
"""

from database.base import Base
from database.config import DatabaseSettings, get_database_settings
from database.engine import check_connection, get_engine, session_scope
from database.models import (
    AnalysisPeriod,
    Company,
    ConceptMapping,
    FactDerivation,
    Filing,
    FinancialFact,
    MetricDefinition,
)

__all__ = [
    "AnalysisPeriod",
    "Base",
    "Company",
    "ConceptMapping",
    "DatabaseSettings",
    "FactDerivation",
    "Filing",
    "FinancialFact",
    "MetricDefinition",
    "check_connection",
    "get_database_settings",
    "get_engine",
    "session_scope",
]
