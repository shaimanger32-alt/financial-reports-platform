"""Seeding reference data into the canonical store.

Seeding runs on every deploy, so it has to be safe to run twice.
"""

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from database.models import ConceptMapping, MetricDefinition
from financial_core.metrics import METRICS_BY_CODE
from ingestion.providers.magna_xbrl.concept_map import CONCEPT_CHAINS
from ingestion.providers.magna_xbrl.concept_map import PROVIDER_CODE_DEFAULT as MAGNA
from ingestion.providers.sec_edgar.concept_map import CONCEPT_CHAINS as SEC_EDGAR_CHAINS
from ingestion.providers.sec_edgar.concept_map import PROVIDER_CODE_DEFAULT as SEC_EDGAR
from ingestion.seeding import seed_reference_data

pytestmark = pytest.mark.integration


def test_seeding_loads_the_catalogue_and_the_chains(session: Session) -> None:
    report = seed_reference_data(session)

    assert report.is_consistent
    assert report.metrics == len(METRICS_BY_CODE)
    assert session.scalar(select(MetricDefinition).where(MetricDefinition.code == "revenue"))


def test_seeding_twice_changes_nothing(session: Session) -> None:
    """Spec section 33. Reference data is upserted, never duplicated."""
    seed_reference_data(session)
    first_metrics = session.query(MetricDefinition).count()
    first_mappings = session.query(ConceptMapping).count()

    seed_reference_data(session)

    assert session.query(MetricDefinition).count() == first_metrics
    assert session.query(ConceptMapping).count() == first_mappings


def test_chain_order_survives_the_round_trip(session: Session) -> None:
    """Priority is the position in the chain, so the precise concept is tried
    first once the data is in the database (decision 0009)."""
    seed_reference_data(session)

    def chain_for(provider: str) -> tuple[str, ...]:
        return tuple(
            session.scalars(
                select(ConceptMapping.raw_concept)
                .where(ConceptMapping.metric_code == "trade_receivables")
                .where(ConceptMapping.provider == provider)
                .where(ConceptMapping.company_id.is_(None))
                .order_by(ConceptMapping.priority)
            ).all()
        )

    # Every provider is seeded, so a chain is only a chain within its own
    # taxonomy. Reading them together would interleave IFRS and us-gaap by
    # priority and destroy the ordering the fallback depends on.
    assert chain_for(MAGNA) == CONCEPT_CHAINS["trade_receivables"]
    assert chain_for(SEC_EDGAR) == SEC_EDGAR_CHAINS["trade_receivables"]
    assert chain_for(MAGNA)[0] == "ifrs-full:CurrentTradeReceivables"


def test_the_taxonomy_namespace_is_recorded(session: Session) -> None:
    """Standard IFRS concepts and issuer extensions have to stay tellable apart."""
    seed_reference_data(session)

    mapping = session.scalar(
        select(ConceptMapping).where(ConceptMapping.raw_concept == "ifrs-full:Revenue")
    )

    assert mapping is not None
    assert mapping.taxonomy == "ifrs-full"


def test_seeding_reports_metrics_that_would_always_be_null(session: Session) -> None:
    """A metric with no chain can never resolve, and the report says so rather
    than leaving it to be discovered later as a permanently empty column."""
    report = seed_reference_data(session)

    assert set(report.metrics_without_chain) == set(METRICS_BY_CODE) - set(CONCEPT_CHAINS)
