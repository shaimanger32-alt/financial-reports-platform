"""Reading the canonical store into the shape the metric engine works with.

This is the only place that bridges the two. `financial_core` stays free of the
database, and the database stays free of financial logic; the translation lives
here.
"""

import uuid
from collections.abc import Sequence

from sqlalchemy import select
from sqlalchemy.orm import Session

from database.models import AnalysisPeriod, Company, ConceptMapping, FinancialFact
from financial_core.metrics import FactPoint, FactSet
from financial_core.periods import FiscalPeriod
from financial_core.quality import QualityStatus


def _to_fiscal_period(row: AnalysisPeriod) -> FiscalPeriod:
    return FiscalPeriod(
        fiscal_year=row.fiscal_year,
        fiscal_quarter=row.fiscal_quarter,
        period_kind=row.period_kind,
        duration_kind=row.duration_kind,
        start=row.period_start,
        end=row.period_end,
    )


def concept_priorities(
    session: Session, provider: str, mapping_version: str = "v1"
) -> dict[str, int]:
    """Position of each raw concept in its metric's fallback chain.

    Carried onto every fact so that, where a company tags two concepts mapping to
    the same metric, the more precise one is the one that gets used.
    """
    rows = session.execute(
        select(ConceptMapping.raw_concept, ConceptMapping.priority).where(
            ConceptMapping.provider == provider,
            ConceptMapping.mapping_version == mapping_version,
            ConceptMapping.company_id.is_(None),
        )
    ).all()
    return {concept: priority for concept, priority in rows}


def load_fact_set(
    session: Session,
    company_id: uuid.UUID,
    *,
    provider: str = "magna_xbrl",
    include_qualities: Sequence[QualityStatus] = (
        QualityStatus.VERIFIED,
        QualityStatus.USABLE_WITH_WARNING,
    ),
) -> FactSet:
    """Every analysable figure for one company.

    Dimensional breakdowns are excluded: a metric is about the consolidated
    total, and a segment figure standing in for it would be quietly wrong.
    Facts with no canonical metric are excluded too — they are kept in the store
    for provenance, but the engine has no name for them.
    """
    priorities = concept_priorities(session, provider)

    rows = session.execute(
        select(FinancialFact, AnalysisPeriod)
        .join(AnalysisPeriod, FinancialFact.period_id == AnalysisPeriod.id)
        .where(
            FinancialFact.company_id == company_id,
            FinancialFact.value.is_not(None),
            FinancialFact.metric_code.is_not(None),
            FinancialFact.dimensions_hash == "",
            FinancialFact.quality_status.in_(list(include_qualities)),
        )
    ).all()

    return FactSet(
        FactPoint(
            metric_code=fact.metric_code or "",
            period=_to_fiscal_period(period),
            value=float(fact.value or 0),
            raw_concept=fact.raw_concept,
            origin=fact.origin,
            quality=fact.quality_status,
            priority=priorities.get(fact.raw_concept, 99),
        )
        for fact, period in rows
    )


def find_company(
    session: Session, provider_entity_id: str, provider: str = "magna_xbrl"
) -> Company | None:
    """Look a company up by the identifier its provider uses."""
    return session.scalar(
        select(Company).where(
            Company.provider == provider,
            Company.provider_entity_id == provider_entity_id,
        )
    )
