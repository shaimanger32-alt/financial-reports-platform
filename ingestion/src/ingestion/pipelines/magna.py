"""Loading a MAGNA fact batch into the canonical store.

The order of operations matters and follows spec section 32:

    company -> filings -> periods -> reported facts -> derived facts

Every step is idempotent. Running the same batch twice leaves the database in
the same state, which is what makes re-ingestion after a code change safe
(spec section 33).

Nothing here decides which of two restated values is "right". Both are stored,
the disagreement is reported, and the choice belongs to the presentation layer
(decision 0009).
"""

import hashlib
import json
import logging
import uuid
from collections import defaultdict
from collections.abc import Sequence
from dataclasses import dataclass, field
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from database.models import AnalysisPeriod, Company, FactDerivation, Filing, FinancialFact
from financial_core.periods import (
    FiscalPeriod,
    classify,
    cumulative_period,
    derive_quarter,
    discrete_period,
    reconcile,
)
from financial_core.provenance import ConsolidationScope, Origin, RecencySource
from financial_core.quality import QualityStatus
from ingestion.pipelines.recency import is_recognised, recency_key
from ingestion.providers.base import FactBatch, ProviderEntity, ProviderFact
from ingestion.providers.magna_xbrl.concept_map import CONCEPT_CHAINS, PROVIDER_CODE_DEFAULT

logger = logging.getLogger(__name__)

# Facts are stored against the concept the issuer used *and* the metric it maps
# to. Choosing between several concepts that map to the same metric is a metric
# engine concern, and happens at calculation time through the resolver.
_METRIC_OF_CONCEPT: dict[str, str] = {
    concept: metric_code for metric_code, chain in CONCEPT_CHAINS.items() for concept in chain
}


@dataclass(frozen=True, slots=True)
class Restatement:
    """The same fact reported differently by two filings."""

    concept: str
    period_code: str
    earlier_filing: str
    earlier_value: Decimal
    later_filing: str
    later_value: Decimal

    @property
    def difference(self) -> Decimal:
        return self.later_value - self.earlier_value


@dataclass(frozen=True, slots=True)
class DerivationMismatch:
    """A quarter the issuer reported and we derived, where the two disagree."""

    concept: str
    period_code: str
    reported: float
    derived: float
    single_filing: bool = True
    """False when the inputs had to be taken from different filings, which is a
    likelier explanation for the gap than an arithmetic problem."""

    @property
    def difference(self) -> float:
        return self.reported - self.derived


@dataclass
class IngestionReport:
    """What one run put in place, and what it noticed."""

    company_id: uuid.UUID | None = None
    filings: int = 0
    periods: int = 0
    reported_facts: int = 0
    derived_facts: int = 0
    skipped_unclassifiable_periods: int = 0
    skipped_dimensional: int = 0
    mixed_vintage_derivations: int = 0
    facts_without_value: int = 0
    unmapped_concepts: set[str] = field(default_factory=set)
    unrecognised_references: set[str] = field(default_factory=set)
    restatements: list[Restatement] = field(default_factory=list)
    derivation_mismatches: list[DerivationMismatch] = field(default_factory=list)

    @property
    def has_warnings(self) -> bool:
        return bool(
            self.restatements
            or self.derivation_mismatches
            or self.unrecognised_references
            or self.skipped_unclassifiable_periods
        )


def dimensions_hash(dimensions: dict[str, str]) -> str:
    """Stable identity for a fact's dimensional breakdown.

    Empty for a consolidated total, which is what the uniqueness constraint
    relies on to keep a breakdown from colliding with the total it belongs to.
    """
    if not dimensions:
        return ""
    canonical = json.dumps(dimensions, sort_keys=True, ensure_ascii=False)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()[:32]


def _upsert_company(session: Session, entity: ProviderEntity, provider: str) -> Company:
    existing = session.scalar(
        select(Company).where(
            Company.provider == provider,
            Company.provider_entity_id == entity.provider_entity_id,
        )
    )
    if existing is not None:
        existing.legal_name = entity.name or existing.legal_name
        existing.display_name = entity.name_en or entity.name or existing.display_name
        existing.name_en = entity.name_en
        existing.sector_code = entity.sector_code
        existing.sector_name = entity.sector_name
        return existing

    company = Company(
        provider=provider,
        provider_entity_id=entity.provider_entity_id,
        legal_name=entity.name,
        display_name=entity.name_en or entity.name,
        name_en=entity.name_en,
        sector_code=entity.sector_code,
        sector_name=entity.sector_name,
        registry_id=entity.provider_entity_id,
    )
    session.add(company)
    session.flush()
    return company


def _upsert_filings(
    session: Session,
    company: Company,
    facts: Sequence[ProviderFact],
    provider: str,
    report: IngestionReport,
) -> dict[str, Filing]:
    """Create a filing row for every reference the facts mention.

    MAGNA has no filing list, so this is the only way filings come into
    existence (decision 0008).
    """
    references = sorted({fact.provider_filing_id for fact in facts})
    existing = {
        filing.provider_filing_id: filing
        for filing in session.scalars(
            select(Filing).where(
                Filing.provider == provider,
                Filing.provider_filing_id.in_(references),
            )
        )
    }

    for reference in references:
        if not is_recognised(reference):
            report.unrecognised_references.add(reference)

        filing = existing.get(reference)
        if filing is None:
            filing = Filing(
                company_id=company.id,
                provider=provider,
                provider_filing_id=reference,
                recency_key=recency_key(reference),
                recency_source=RecencySource.INFERRED,
                source_format="ixbrl",
            )
            session.add(filing)
            existing[reference] = filing
            report.filings += 1

    session.flush()
    return existing


def _upsert_period(
    session: Session,
    company: Company,
    period: FiscalPeriod,
    cache: dict[str, AnalysisPeriod],
    report: IngestionReport,
) -> AnalysisPeriod:
    cached = cache.get(period.code)
    if cached is not None:
        return cached

    existing = session.scalar(
        select(AnalysisPeriod).where(
            AnalysisPeriod.company_id == company.id,
            AnalysisPeriod.code == period.code,
        )
    )
    if existing is None:
        existing = AnalysisPeriod(
            company_id=company.id,
            code=period.code,
            fiscal_year=period.fiscal_year,
            fiscal_quarter=period.fiscal_quarter,
            period_kind=period.period_kind,
            duration_kind=period.duration_kind,
            period_start=period.start,
            period_end=period.end,
        )
        session.add(existing)
        session.flush()
        report.periods += 1

    cache[period.code] = existing
    return existing


def _load_reported_facts(
    session: Session,
    company: Company,
    facts: Sequence[ProviderFact],
    filings: dict[str, Filing],
    report: IngestionReport,
) -> None:
    period_cache: dict[str, AnalysisPeriod] = {}

    existing_keys = {
        (fact.filing_id, fact.raw_concept, fact.period_id, fact.dimensions_hash, fact.origin)
        for fact in session.scalars(
            select(FinancialFact).where(FinancialFact.company_id == company.id)
        )
    }

    for provider_fact in facts:
        fiscal_period = classify(provider_fact.period.start, provider_fact.period.end)
        if fiscal_period is None:
            report.skipped_unclassifiable_periods += 1
            logger.debug(
                "period %r on %s is not a calendar quarter shape; skipped",
                provider_fact.period.raw,
                provider_fact.concept,
            )
            continue

        if provider_fact.is_dimensional:
            report.skipped_dimensional += 1

        if provider_fact.value is None:
            report.facts_without_value += 1

        metric_code = _METRIC_OF_CONCEPT.get(provider_fact.concept)
        if metric_code is None:
            report.unmapped_concepts.add(provider_fact.concept)

        period = _upsert_period(session, company, fiscal_period, period_cache, report)
        filing = filings[provider_fact.provider_filing_id]
        digest = dimensions_hash(provider_fact.dimensions)

        key = (filing.id, provider_fact.concept, period.id, digest, Origin.REPORTED)
        if key in existing_keys:
            continue
        existing_keys.add(key)

        session.add(
            FinancialFact(
                company_id=company.id,
                filing_id=filing.id,
                period_id=period.id,
                origin=Origin.REPORTED,
                raw_concept=provider_fact.concept,
                metric_code=metric_code,
                value=None if provider_fact.value is None else Decimal(str(provider_fact.value)),
                currency=provider_fact.unit,
                unit=provider_fact.unit,
                scale=provider_fact.scale,
                decimals=provider_fact.decimals,
                statement=provider_fact.statement,
                consolidation_scope=(
                    ConsolidationScope.CONSOLIDATED
                    if provider_fact.statement and "Consolidated" in provider_fact.statement
                    else ConsolidationScope.UNKNOWN
                ),
                dimensions_json=provider_fact.dimensions or None,
                dimensions_hash=digest,
            )
        )
        report.reported_facts += 1

    session.flush()


def _detect_restatements(session: Session, company: Company, report: IngestionReport) -> None:
    """Find facts that two filings disagree about.

    Both values stay. The newer filing is flagged so a comparability warning can
    be raised later (spec section 21.3), and the difference is reported.
    """
    rows = session.execute(
        select(FinancialFact, Filing, AnalysisPeriod)
        .join(Filing, FinancialFact.filing_id == Filing.id)
        .join(AnalysisPeriod, FinancialFact.period_id == AnalysisPeriod.id)
        .where(
            FinancialFact.company_id == company.id,
            FinancialFact.origin == Origin.REPORTED,
            FinancialFact.value.is_not(None),
            FinancialFact.dimensions_hash == "",
        )
    ).all()

    grouped: dict[tuple[str, str], list[tuple[FinancialFact, Filing]]] = defaultdict(list)
    for fact, filing, period in rows:
        grouped[(fact.raw_concept, period.code)].append((fact, filing))

    for (concept, period_code), entries in grouped.items():
        values = {entry[0].value for entry in entries}
        if len(values) < 2:
            continue

        ordered = sorted(entries, key=lambda entry: entry[1].recency_key)
        earlier_fact, earlier_filing = ordered[0]
        later_fact, later_filing = ordered[-1]
        if earlier_fact.value == later_fact.value:
            continue

        later_filing.is_restatement = True
        if later_filing.supersedes_filing_id is None:
            later_filing.supersedes_filing_id = earlier_filing.id

        assert earlier_fact.value is not None and later_fact.value is not None
        report.restatements.append(
            Restatement(
                concept=concept,
                period_code=period_code,
                earlier_filing=earlier_filing.provider_filing_id,
                earlier_value=earlier_fact.value,
                later_filing=later_filing.provider_filing_id,
                later_value=later_fact.value,
            )
        )

    session.flush()


def _current_values(
    session: Session, company: Company
) -> dict[tuple[str, str], tuple[FinancialFact, Filing]]:
    """The most recently filed value for each concept and period.

    Where a fact was restated, the newest filing wins. The superseded value is
    still in the database; this is only about which figure a derivation is built
    on (decision 0009).
    """
    rows = session.execute(
        select(FinancialFact, Filing, AnalysisPeriod)
        .join(Filing, FinancialFact.filing_id == Filing.id)
        .join(AnalysisPeriod, FinancialFact.period_id == AnalysisPeriod.id)
        .where(
            FinancialFact.company_id == company.id,
            FinancialFact.origin == Origin.REPORTED,
            FinancialFact.value.is_not(None),
            FinancialFact.dimensions_hash == "",
        )
    ).all()

    latest: dict[tuple[str, str], tuple[FinancialFact, Filing]] = {}
    for fact, filing, period in rows:
        key = (fact.raw_concept, period.code)
        held = latest.get(key)
        if held is None or filing.recency_key > held[1].recency_key:
            latest[key] = (fact, filing)
    return latest


def _by_filing(
    session: Session, company: Company
) -> tuple[dict[str, dict[tuple[str, str], FinancialFact]], dict[str, Filing]]:
    """Reported facts grouped by the filing that carried them.

    A single filing is internally consistent: the cumulative figures it publishes
    agree with the standalone quarter it publishes. Figures taken from two
    different filings need not, because the later one may have reclassified
    something without re-tagging the earlier period.
    """
    rows = session.execute(
        select(FinancialFact, Filing, AnalysisPeriod)
        .join(Filing, FinancialFact.filing_id == Filing.id)
        .join(AnalysisPeriod, FinancialFact.period_id == AnalysisPeriod.id)
        .where(
            FinancialFact.company_id == company.id,
            FinancialFact.origin == Origin.REPORTED,
            FinancialFact.value.is_not(None),
            FinancialFact.dimensions_hash == "",
        )
    ).all()

    grouped: dict[str, dict[tuple[str, str], FinancialFact]] = defaultdict(dict)
    filings: dict[str, Filing] = {}
    for fact, filing, period in rows:
        grouped[filing.recency_key][(fact.raw_concept, period.code)] = fact
        filings[filing.recency_key] = filing
    return grouped, filings


def _derive_quarters(session: Session, company: Company, report: IngestionReport) -> None:
    """Create the standalone quarters that follow from cumulative reporting.

    Q4 exists only this way. Q2 and Q3 are also derived even though issuers
    report them, so the two can be compared -- that comparison is the only
    evidence that the arithmetic Q4 depends on is sound (decision 0009).

    Inputs are taken from a single filing whenever one carries both, because a
    filing is internally consistent and a pair drawn from two is not. Hilan's
    2022 finance costs are the case in point: the half-year filing reports
    18,694,000 while the nine-month filing implies 14,097,000 for the same
    period, so differencing across the two produces a quarter that is nearly
    four times too small. Where no single filing has both inputs the derivation
    still happens, marked `usable_with_warning`.
    """
    latest = _current_values(session, company)
    grouped, filings_by_key = _by_filing(session, company)
    filing_keys = sorted(grouped, reverse=True)
    period_cache: dict[str, AnalysisPeriod] = {}

    # Balance sheet instants cannot be reached from here: their period codes are
    # of the form 2023-Q3-AT-2023-09-30 and never match a cumulative code, so
    # no balance can be differenced into a quarter. That is the stock/flow rule
    # from spec section 11.3, enforced by construction rather than by care.
    concepts = {concept for concept, _ in latest}
    years = {int(code.split("-", 1)[0]) for _, code in latest if code.split("-", 1)[0].isdigit()}

    existing_derived = {
        (fact.raw_concept, fact.period_id)
        for fact in session.scalars(
            select(FinancialFact).where(
                FinancialFact.company_id == company.id,
                FinancialFact.origin == Origin.DERIVED,
            )
        )
    }

    for concept in sorted(concepts):
        for year in sorted(years):
            for quarter in (2, 3, 4):
                required = [cumulative_period(year, quarter).code]
                if quarter > 1:
                    required.append(cumulative_period(year, quarter - 1).code)

                source_key = next(
                    (
                        key
                        for key in filing_keys
                        if all((concept, code) in grouped[key] for code in required)
                    ),
                    None,
                )
                single_filing = source_key is not None

                if single_filing:
                    assert source_key is not None
                    facts_here = grouped[source_key]

                    def lookup(
                        period: FiscalPeriod,
                        _concept: str = concept,
                        _facts: dict[tuple[str, str], FinancialFact] = facts_here,
                    ) -> float | None:
                        held = _facts.get((_concept, period.code))
                        return None if held is None else float(held.value or 0)

                    def fact_for(
                        code: str,
                        _concept: str = concept,
                        _facts: dict[tuple[str, str], FinancialFact] = facts_here,
                    ) -> FinancialFact:
                        return _facts[(_concept, code)]
                else:

                    def lookup(period: FiscalPeriod, _concept: str = concept) -> float | None:  # type: ignore[misc]
                        held = latest.get((_concept, period.code))
                        return None if held is None else float(held[0].value or 0)

                    def fact_for(code: str, _concept: str = concept) -> FinancialFact:  # type: ignore[misc]
                        return latest[(_concept, code)][0]

                derivation = derive_quarter(year, quarter, lookup)
                if derivation is None:
                    continue

                if not single_filing:
                    report.mixed_vintage_derivations += 1

                target = discrete_period(year, quarter)
                reported_entry = latest.get((concept, target.code))
                if reported_entry is not None:
                    # The issuer's rounding granularity, so tagging to the
                    # nearest thousand is not mistaken for a disagreement.
                    outcome = reconcile(
                        target,
                        reported=float(reported_entry[0].value or 0),
                        derived=derivation.value,
                        decimals=reported_entry[0].decimals,
                    )
                    if outcome.agrees is False:
                        report.derivation_mismatches.append(
                            DerivationMismatch(
                                concept=concept,
                                period_code=target.code,
                                reported=outcome.reported or 0.0,
                                derived=outcome.derived or 0.0,
                                single_filing=single_filing,
                            )
                        )

                period_row = _upsert_period(session, company, target, period_cache, report)
                if (concept, period_row.id) in existing_derived:
                    continue
                existing_derived.add((concept, period_row.id))

                source_fact = fact_for(derivation.inputs[0][0].code)
                source_filing = (
                    filings_by_key[source_key]
                    if source_key is not None
                    else latest[(concept, derivation.inputs[0][0].code)][1]
                )
                derived_fact = FinancialFact(
                    company_id=company.id,
                    filing_id=source_filing.id,
                    period_id=period_row.id,
                    origin=Origin.DERIVED,
                    raw_concept=concept,
                    metric_code=_METRIC_OF_CONCEPT.get(concept),
                    value=Decimal(str(derivation.value)),
                    currency=source_fact.currency,
                    unit=source_fact.unit,
                    scale=source_fact.scale,
                    statement=source_fact.statement,
                    consolidation_scope=source_fact.consolidation_scope,
                    dimensions_hash="",
                    derivation_formula=derivation.formula,
                    quality_status=(
                        QualityStatus.VERIFIED
                        if single_filing
                        else QualityStatus.USABLE_WITH_WARNING
                    ),
                )
                session.add(derived_fact)
                session.flush()

                for ordinal, (input_period, _) in enumerate(derivation.inputs):
                    input_fact = fact_for(input_period.code)
                    session.add(
                        FactDerivation(
                            derived_fact_id=derived_fact.id,
                            input_fact_id=input_fact.id,
                            role="minuend" if ordinal == 0 else "subtrahend",
                            ordinal=ordinal,
                        )
                    )
                report.derived_facts += 1

    session.flush()


def ingest_batch(
    session: Session,
    entity: ProviderEntity,
    batch: FactBatch,
    provider: str = PROVIDER_CODE_DEFAULT,
) -> IngestionReport:
    """Load one company's facts, end to end.

    Idempotent: the same batch applied twice produces the same rows.
    """
    report = IngestionReport()

    facts = [fact for fact in batch.facts if fact.provider_entity_id == entity.provider_entity_id]
    if not facts:
        logger.warning("batch contains no facts for %s", entity.provider_entity_id)
        return report

    company = _upsert_company(session, entity, provider)
    report.company_id = company.id

    filings = _upsert_filings(session, company, facts, provider, report)
    _load_reported_facts(session, company, facts, filings, report)
    _detect_restatements(session, company, report)
    _derive_quarters(session, company, report)

    if report.unmapped_concepts:
        logger.info(
            "%d concepts have no canonical mapping and were stored raw",
            len(report.unmapped_concepts),
        )
    return report


__all__ = [
    "DerivationMismatch",
    "IngestionReport",
    "Restatement",
    "dimensions_hash",
    "ingest_batch",
]
