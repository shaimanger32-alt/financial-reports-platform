"""Loading an SEC EDGAR fact batch into the canonical store.

The order of operations is the MAGNA pipeline's, from spec section 32:

    company -> fiscal calendar -> filings -> periods -> reported facts -> derived

Three things differ, and each is a property of the American market rather than
of the code:

**The fiscal calendar has to be learned first.** An Israeli issuer closes on
31 December and a period can be read off its dates. Apple's fiscal year is 52 or
53 weeks and ends on the last Saturday of September, so nothing can be
classified until the company's own years are reconstructed from its filings.

**Every quarter is derived, not just the fourth.** Israeli issuers report the
second and third quarters discretely. American filers report cash flow
cumulatively and almost nothing discretely, so `Qn = YTD(n) - YTD(n-1)` runs for
each quarter. Validated against the quarters Apple *does* publish separately:
nine of nine, exactly.

**Publication is a separate act.** A company arrives unpublished. Loading it and
putting it in front of a reader are different decisions, and only one of them
is this pipeline's.
"""

import logging
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from database.models import AnalysisPeriod, Company, FactDerivation, Filing, FinancialFact
from financial_core.periods import (
    FiscalCalendar,
    FiscalPeriod,
    classify_in,
    derive_quarter,
    discrete_period_in,
)
from financial_core.provenance import Origin, RecencySource
from financial_core.quality import QualityStatus
from ingestion.providers.base import FactBatch, ProviderEntity, ProviderFact
from ingestion.providers.sec_edgar.concept_map import CONCEPT_CHAINS, PROVIDER_CODE_DEFAULT

logger = logging.getLogger(__name__)

MARKET = "us_gaap"

CURRENCY_CODE_LENGTH = 3


def _currency_of(unit: str | None) -> str | None:
    """The unit, when it is a currency at all.

    EDGAR reports share counts in a unit of `shares` and ratios in `pure`. Those
    are units, not currencies, and writing them into a currency column would
    both overflow it and assert something false about the figure.
    """
    if unit is None:
        return None
    return unit if len(unit) == CURRENCY_CODE_LENGTH and unit.isalpha() else None


# Concept to the metric it maps to, and its position in the chain. Position is
# stored on the fact so the resolver can prefer the more precise concept later
# without re-reading the chain (decision 0009).
_CHAIN_POSITION: dict[str, tuple[str, int]] = {
    concept: (metric_code, position)
    for metric_code, chain in CONCEPT_CHAINS.items()
    for position, concept in enumerate(chain)
}


@dataclass(slots=True)
class EdgarIngestionReport:
    """What one ingestion run put in place."""

    company: str = ""
    fiscal_years: int = 0
    projected_years: int = 0
    filings: int = 0
    periods: int = 0
    reported_facts: int = 0
    derived_facts: int = 0
    unclassified: int = 0
    unmapped_concepts: set[str] = field(default_factory=set)

    @property
    def facts(self) -> int:
        return self.reported_facts + self.derived_facts


def _upsert_company(
    session: Session,
    entity: ProviderEntity,
    calendar: FiscalCalendar,
) -> Company:
    """Create or refresh the company row, and store the calendar it declared.

    `is_published` is set only on creation, and only to false. A company that
    someone has already chosen to publish is not un-published by a re-ingest.
    """
    existing = session.scalar(
        select(Company).where(
            Company.provider == PROVIDER_CODE_DEFAULT,
            Company.provider_entity_id == entity.provider_entity_id,
        )
    )
    calendar_json: dict[str, object] = {
        "windows": [
            {
                "fiscal_year": window.fiscal_year,
                "start": window.start.isoformat(),
                "end": window.end.isoformat(),
                "is_projected": window.is_projected,
            }
            for window in calendar.windows
        ]
    }

    if existing is not None:
        existing.legal_name = entity.name or existing.legal_name
        existing.display_name = entity.name_en or entity.name or existing.display_name
        existing.name_en = entity.name_en
        existing.fiscal_calendar_json = calendar_json
        return existing

    company = Company(
        provider=PROVIDER_CODE_DEFAULT,
        provider_entity_id=entity.provider_entity_id,
        legal_name=entity.name,
        display_name=entity.name_en or entity.name,
        name_en=entity.name_en,
        registry_id=entity.provider_entity_id,
        country="US",
        reporting_currency="USD",
        market=MARKET,
        is_published=False,
        fiscal_calendar_json=calendar_json,
    )
    session.add(company)
    session.flush()
    return company


def load_fiscal_calendar(company: Company) -> FiscalCalendar:
    """Rebuild the stored calendar. Empty when the company has none recorded."""
    from financial_core.periods import FiscalYearWindow

    stored = company.fiscal_calendar_json or {}
    windows = stored.get("windows", []) if isinstance(stored, dict) else []
    if not isinstance(windows, list):
        return FiscalCalendar(())

    return FiscalCalendar(
        tuple(
            FiscalYearWindow(
                fiscal_year=int(window["fiscal_year"]),
                start=date.fromisoformat(str(window["start"])),
                end=date.fromisoformat(str(window["end"])),
                is_projected=bool(window.get("is_projected", False)),
            )
            for window in windows
            if isinstance(window, dict)
        )
    )


def _upsert_filings(
    session: Session,
    company: Company,
    facts: Sequence[ProviderFact],
    report: EdgarIngestionReport,
) -> dict[str, Filing]:
    """One filing row per accession number the facts mention.

    Unlike MAGNA, recency is not inferred. SEC states a `filed` date on every
    fact, so the filing carries a real publication date and decision 0009's
    reference-number inference does not apply here.
    """
    filed_by_reference: dict[str, str] = {}
    for fact in facts:
        reference = fact.provider_filing_id
        if not reference:
            continue
        filed = fact.labels.get("filed") or ""
        held = filed_by_reference.get(reference)
        if held is None or filed > held:
            filed_by_reference[reference] = filed

    existing = {
        filing.provider_filing_id: filing
        for filing in session.scalars(
            select(Filing).where(
                Filing.provider == PROVIDER_CODE_DEFAULT,
                Filing.provider_filing_id.in_(list(filed_by_reference)),
            )
        )
    }

    for reference, filed in sorted(filed_by_reference.items()):
        if reference in existing:
            continue
        filing = Filing(
            company_id=company.id,
            provider=PROVIDER_CODE_DEFAULT,
            provider_filing_id=reference,
            recency_key=filed or reference,
            recency_source=RecencySource.PROVIDER,
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
    report: EdgarIngestionReport,
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
    elif (existing.period_start, existing.period_end) != (period.start, period.end):
        # Dates can improve. Derived quarters were once given calendar
        # boundaries, and a re-ingest that learned the company's own must be
        # able to correct them rather than leave a wrong date on the page.
        existing.period_start = period.start
        existing.period_end = period.end
        session.flush()

    cache[period.code] = existing
    return existing


def _load_reported_facts(
    session: Session,
    company: Company,
    facts: Sequence[ProviderFact],
    filings: dict[str, Filing],
    calendar: FiscalCalendar,
    report: EdgarIngestionReport,
) -> dict[str, AnalysisPeriod]:
    """Store every fact whose period the company's own calendar recognises.

    A period outside every declared fiscal year is skipped rather than assigned
    to a neighbouring one. Those are comparative opening balances that predate
    the earliest year the company has filed, and inventing boundaries for them
    would put a figure in a quarter it may not belong to.
    """
    period_cache: dict[str, AnalysisPeriod] = {}

    existing_keys = {
        (fact.filing_id, fact.raw_concept, fact.period_id, fact.origin)
        for fact in session.scalars(
            select(FinancialFact).where(FinancialFact.company_id == company.id)
        )
    }

    for provider_fact in facts:
        fiscal_period = classify_in(provider_fact.period.start, provider_fact.period.end, calendar)
        if fiscal_period is None:
            report.unclassified += 1
            continue

        mapped = _CHAIN_POSITION.get(provider_fact.concept)
        if mapped is None:
            report.unmapped_concepts.add(provider_fact.concept)
            continue
        metric_code, _position = mapped

        filing = filings.get(provider_fact.provider_filing_id)
        if filing is None:
            continue

        period = _upsert_period(session, company, fiscal_period, period_cache, report)
        key = (filing.id, provider_fact.concept, period.id, Origin.REPORTED)
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
                currency=_currency_of(provider_fact.unit),
                unit=provider_fact.unit,
                quality_status=QualityStatus.VERIFIED,
            )
        )
        report.reported_facts += 1

    session.flush()
    return period_cache


def _derive_quarters(
    session: Session,
    company: Company,
    calendar: FiscalCalendar,
    period_cache: dict[str, AnalysisPeriod],
    report: EdgarIngestionReport,
) -> None:
    """Difference cumulative figures into discrete quarters.

    Every quarter, not only the fourth: American filers report cash flow
    year-to-date and rarely publish a standalone quarter at all.

    A derived quarter is stored as `usable_with_warning`, never `verified`. Its
    two inputs come from two different filings whenever no single filing carries
    both, and filings do not always agree with each other -- the property that
    made every Israeli Q4 `usable_with_warning` too.
    """
    values: dict[tuple[str, str], float] = {}
    source: dict[tuple[str, str], FinancialFact] = {}
    rows = session.execute(
        select(FinancialFact, AnalysisPeriod)
        .join(AnalysisPeriod, FinancialFact.period_id == AnalysisPeriod.id)
        .where(
            FinancialFact.company_id == company.id,
            FinancialFact.origin == Origin.REPORTED,
            FinancialFact.value.is_not(None),
        )
    ).all()
    for fact, period in rows:
        if fact.metric_code and fact.value is not None:
            key = (fact.metric_code, period.code)
            values.setdefault(key, float(fact.value))
            source.setdefault(key, fact)

    existing_derived = {
        (fact.metric_code, fact.period_id)
        for fact in session.scalars(
            select(FinancialFact).where(
                FinancialFact.company_id == company.id,
                FinancialFact.origin == Origin.DERIVED,
            )
        )
    }

    for metric_code in CONCEPT_CHAINS:
        for window in calendar.windows:
            for quarter in (1, 2, 3, 4):
                # The company's own dates, not the calendar's. A derived quarter
                # has none of its own, and taking them from the calendar stored
                # Apple's fiscal Q4 as October to December when the company
                # closed it in September.
                target = discrete_period_in(window, quarter)
                if (metric_code, target.code) in values:
                    continue  # the company reported this quarter itself

                derivation = derive_quarter(
                    window.fiscal_year,
                    quarter,
                    _lookup_for(values, metric_code),
                )
                if derivation is None:
                    continue

                inputs = [source[(metric_code, key.code)] for key, _ in derivation.inputs]
                minuend = inputs[0]

                period = _upsert_period(session, company, target, period_cache, report)
                if (metric_code, period.id) in existing_derived:
                    continue
                existing_derived.add((metric_code, period.id))

                # Attributed to the filing the first input came from. A derived
                # figure still has to point at a document a reader can open
                # (spec section 4.2).
                derived = FinancialFact(
                    company_id=company.id,
                    filing_id=minuend.filing_id,
                    period_id=period.id,
                    origin=Origin.DERIVED,
                    raw_concept=minuend.raw_concept,
                    metric_code=metric_code,
                    value=Decimal(str(derivation.value)),
                    currency=minuend.currency,
                    unit=minuend.unit,
                    quality_status=QualityStatus.USABLE_WITH_WARNING,
                    derivation_formula=derivation.formula,
                )
                session.add(derived)
                session.flush()

                for ordinal, input_fact in enumerate(inputs):
                    session.add(
                        FactDerivation(
                            derived_fact_id=derived.id,
                            input_fact_id=input_fact.id,
                            role="minuend" if ordinal == 0 else "subtrahend",
                            ordinal=ordinal,
                        )
                    )
                report.derived_facts += 1

    session.flush()


def _lookup_for(
    values: dict[tuple[str, str], float], metric_code: str
) -> Callable[[FiscalPeriod], float | None]:
    """Bind the metric so the closure cannot capture a loop variable."""

    def lookup(period: FiscalPeriod) -> float | None:
        return values.get((metric_code, period.code))

    return lookup


def ingest_batch(
    session: Session,
    entity: ProviderEntity,
    batch: FactBatch,
    calendar: FiscalCalendar,
) -> EdgarIngestionReport:
    """Load one company's facts. Idempotent: running it twice changes nothing."""
    report = EdgarIngestionReport(
        company=entity.name,
        fiscal_years=len(calendar.windows),
        projected_years=sum(1 for window in calendar.windows if window.is_projected),
    )
    if calendar.is_empty:
        logger.warning("%s declared no fiscal years; nothing can be classified", entity.name)
        return report

    company = _upsert_company(session, entity, calendar)
    filings = _upsert_filings(session, company, batch.facts, report)
    period_cache = _load_reported_facts(session, company, batch.facts, filings, calendar, report)
    _derive_quarters(session, company, calendar, period_cache, report)
    return report
