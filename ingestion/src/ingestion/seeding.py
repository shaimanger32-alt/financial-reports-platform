"""Loading reference data into the canonical store.

Metric definitions come from the domain catalogue; concept chains come from the
provider. Both are versioned data rather than code (spec section 33), so they
live in the database once loaded and a change to a chain does not silently
rewrite what a past analysis meant.

Seeding is idempotent. Running it twice leaves the same rows.
"""

import logging
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from database.models import ConceptMapping, MetricDefinition
from financial_core.metrics import REPORTED_METRICS
from ingestion.providers.magna_xbrl.concept_map import (
    CONCEPT_CHAINS,
    MAPPING_VERSION,
    PROVIDER_CODE_DEFAULT,
)

logger = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class SeedReport:
    """What a seeding run put in place."""

    metrics: int
    mappings: int
    metrics_without_chain: tuple[str, ...]
    chains_without_metric: tuple[str, ...]

    @property
    def is_consistent(self) -> bool:
        """Whether every chain names a real metric.

        A chain pointing at a metric that does not exist is a typo that would
        otherwise surface much later as a permanently null figure.
        """
        return not self.chains_without_metric


def seed_metric_definitions(session: Session) -> int:
    """Upsert the canonical metric catalogue."""
    rows = [
        {
            "code": spec.code,
            "display_name_he": spec.name_he,
            "display_name_en": spec.name_en,
            "description_he": spec.note,
            "description_en": spec.note,
            "category": spec.category.value,
            "metric_type": "reported",
            "unit_type": spec.unit_type.value,
            "sector_scope": "general",
            "is_core": spec.is_core,
        }
        for spec in REPORTED_METRICS
    ]

    statement = insert(MetricDefinition).values(rows)
    statement = statement.on_conflict_do_update(
        index_elements=[MetricDefinition.code],
        set_={
            "display_name_he": statement.excluded.display_name_he,
            "display_name_en": statement.excluded.display_name_en,
            "description_he": statement.excluded.description_he,
            "description_en": statement.excluded.description_en,
            "category": statement.excluded.category,
            "unit_type": statement.excluded.unit_type,
            "is_core": statement.excluded.is_core,
        },
    )
    session.execute(statement)
    return len(rows)


def seed_concept_mappings(session: Session, provider: str = PROVIDER_CODE_DEFAULT) -> int:
    """Upsert the ordered fallback chains for a provider.

    Priority is the position in the chain, so the most precise concept is tried
    first (decision 0009).
    """
    rows = [
        {
            "provider": provider,
            "taxonomy": concept.split(":", 1)[0] if ":" in concept else None,
            "raw_concept": concept,
            "metric_code": metric_code,
            "priority": position,
            "company_id": None,
            "mapping_version": MAPPING_VERSION,
        }
        for metric_code, chain in CONCEPT_CHAINS.items()
        for position, concept in enumerate(chain)
    ]

    statement = insert(ConceptMapping).values(rows)
    statement = statement.on_conflict_do_update(
        constraint="uq_mapping_concept_scope_version",
        set_={
            "metric_code": statement.excluded.metric_code,
            "priority": statement.excluded.priority,
            "taxonomy": statement.excluded.taxonomy,
        },
    )
    session.execute(statement)
    return len(rows)


def seed_reference_data(session: Session, provider: str = PROVIDER_CODE_DEFAULT) -> SeedReport:
    """Load metric definitions and concept chains, and check they agree."""
    metric_count = seed_metric_definitions(session)
    session.flush()
    mapping_count = seed_concept_mappings(session, provider)
    session.flush()

    known_codes = set(session.scalars(select(MetricDefinition.code)))
    chain_codes = set(CONCEPT_CHAINS)

    report = SeedReport(
        metrics=metric_count,
        mappings=mapping_count,
        metrics_without_chain=tuple(sorted(known_codes - chain_codes)),
        chains_without_metric=tuple(sorted(chain_codes - known_codes)),
    )

    if report.metrics_without_chain:
        logger.warning(
            "metrics with no concept chain, and therefore always null: %s",
            ", ".join(report.metrics_without_chain),
        )
    if report.chains_without_metric:
        logger.error(
            "concept chains naming an unknown metric: %s",
            ", ".join(report.chains_without_metric),
        )

    return report
