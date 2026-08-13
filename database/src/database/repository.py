"""Reading the canonical store into the shape the metric engine works with.

This is the only place that bridges the two. `financial_core` stays free of the
database, and the database stays free of financial logic; the translation lives
here.
"""

import uuid
from collections import defaultdict
from collections.abc import Sequence
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from database.models import AnalysisPeriod, Company, ConceptMapping, Filing, FinancialFact
from database.models import AnalysisSnapshot as AnalysisSnapshotRow
from financial_core.metrics import CALCULATED_BY_CODE, FactPoint, FactSet
from financial_core.periods import (
    DurationKind,
    FiscalPeriod,
    cumulative_period,
    discrete_period,
)
from financial_core.provenance import Origin
from financial_core.quality import QualityStatus
from financial_core.signals import MetricObservation, MetricSeries
from financial_core.validation import Observation


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
        select(FinancialFact, AnalysisPeriod, Filing.recency_key)
        .join(AnalysisPeriod, FinancialFact.period_id == AnalysisPeriod.id)
        .join(Filing, FinancialFact.filing_id == Filing.id)
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
            # Decision 0009: a restatement supersedes what it restates, and the
            # filing's recency is how the store knows which is which.
            recency=recency or "",
        )
        for fact, period, recency in rows
    )


def find_company(
    session: Session, provider_entity_id: str, provider: str | None = None
) -> Company | None:
    """Look a company up by the identifier its provider uses.

    `provider` is optional now that there are two of them. A registrar number
    and a CIK cannot collide -- one is Israeli and the other American -- so a
    caller holding only the public identifier does not have to know which source
    the company came from.
    """
    statement = select(Company).where(Company.provider_entity_id == provider_entity_id)
    if provider is not None:
        statement = statement.where(Company.provider == provider)
    return session.scalar(statement)


def load_metric_series(
    session: Session,
    company_id: uuid.UUID,
    metric_codes: Sequence[str],
    quarters: int = 16,
) -> dict[str, MetricSeries]:
    """Build a quarterly history for each metric, oldest first.

    The signal engine compares each period against the same quarter a year
    earlier, so the series must be contiguous: a gap has to appear as a period
    with no value rather than as a missing entry, or the year-on-year offset
    would silently line up against the wrong quarter.
    """
    facts = load_fact_set(session, company_id)

    latest = max(
        (period for period in facts.periods(duration_kind=DurationKind.QUARTER)),
        default=None,
    )
    if latest is None:
        return {}

    timeline: list[FiscalPeriod] = []
    year, quarter = latest.fiscal_year, latest.fiscal_quarter
    for _ in range(quarters):
        timeline.append(discrete_period(year, quarter))
        quarter -= 1
        if quarter == 0:
            quarter, year = 4, year - 1
    timeline.reverse()

    series: dict[str, MetricSeries] = {}
    for code in metric_codes:
        observations = tuple(
            MetricObservation(period, compute(code, facts, period)) for period in timeline
        )
        series[code] = MetricSeries(metric_code=code, observations=observations)
    return series


def load_annual_metric_series(
    session: Session,
    company_id: uuid.UUID,
    metric_codes: Sequence[str],
    years: int = 10,
) -> dict[str, MetricSeries]:
    """The same, one observation per fiscal year.

    A year-on-year comparison on an annual series is the previous year, not four
    entries back, which is what `periods_per_year` on the series carries. Passing
    a quarterly series where an annual one belongs would compare a full year
    against a single quarter and produce a confident, meaningless number.
    """
    facts = load_fact_set(session, company_id)

    latest = max(
        (period for period in facts.periods(duration_kind=DurationKind.ANNUAL)),
        default=None,
    )
    if latest is None:
        return {}

    timeline = [
        cumulative_period(year, 4)
        for year in range(latest.fiscal_year - years + 1, latest.fiscal_year + 1)
    ]

    series: dict[str, MetricSeries] = {}
    for code in metric_codes:
        observations = tuple(
            MetricObservation(period, compute(code, facts, period)) for period in timeline
        )
        series[code] = MetricSeries(metric_code=code, observations=observations, periods_per_year=1)
    return series


@dataclass(frozen=True, slots=True)
class Restatement:
    """The same figure, reported differently by two of a company's own filings."""

    metric_code: str
    period_code: str
    raw_concept: str
    superseded_value: float
    current_value: float
    superseded_filing: str
    current_filing: str

    @property
    def difference(self) -> float:
        return self.current_value - self.superseded_value

    @property
    def relative_difference(self) -> float | None:
        scale = max(abs(self.superseded_value), abs(self.current_value))
        return None if scale == 0.0 else self.difference / scale


def restatements(
    session: Session, company_id: uuid.UUID, *, provider: str = "magna_xbrl"
) -> dict[str, list[Restatement]]:
    """Figures a later filing reported differently, keyed by period code.

    Decision 0009 keeps both values and says the disagreement is **surfaced,
    never resolved silently**. The store does now prefer the later filing when
    it calculates -- which is right, and is exactly why this has to be reported:
    otherwise a figure changes underneath a reader with nothing said.

    Apple is the case that made it concrete. It filed fiscal 2009 revenue as
    $36.5bn, then restated it to $42.9bn in every later filing after adopting
    the new revenue recognition standard. Reading one against the other put
    fiscal 2010 growth at +78.5% when the company's own restated comparative
    gives +52%.
    """
    priorities = concept_priorities(session, provider)

    rows = session.execute(
        select(FinancialFact, AnalysisPeriod.code, Filing.recency_key, Filing.provider_filing_id)
        .join(AnalysisPeriod, FinancialFact.period_id == AnalysisPeriod.id)
        .join(Filing, FinancialFact.filing_id == Filing.id)
        .where(
            FinancialFact.company_id == company_id,
            FinancialFact.origin == Origin.REPORTED,
            FinancialFact.value.is_not(None),
            FinancialFact.metric_code.is_not(None),
            FinancialFact.dimensions_hash == "",
        )
    ).all()

    # Grouped by the concept as well as the metric: two concepts mapping to one
    # metric are not a restatement, they are a fallback chain doing its job.
    grouped: dict[tuple[str, str, str], list[tuple[str, str, float]]] = defaultdict(list)
    for fact, period_code, recency, reference in rows:
        grouped[(fact.metric_code or "", period_code, fact.raw_concept or "")].append(
            (recency or "", reference, float(fact.value or 0))
        )

    found: dict[str, list[Restatement]] = defaultdict(list)
    for (metric_code, period_code, concept), entries in grouped.items():
        if len({value for _, _, value in entries}) < 2:
            continue
        ordered = sorted(entries)
        earliest, latest = ordered[0], ordered[-1]
        if earliest[2] == latest[2]:
            continue
        found[period_code].append(
            Restatement(
                metric_code=metric_code,
                period_code=period_code,
                raw_concept=concept,
                superseded_value=earliest[2],
                current_value=latest[2],
                superseded_filing=earliest[1],
                current_filing=latest[1],
            )
        )

    for entries_list in found.values():
        entries_list.sort(key=lambda r: r.metric_code)
    # `priorities` is read so a future refinement can prefer the precise concept.
    del priorities
    return dict(found)


def reported_observations(session: Session, company_id: uuid.UUID) -> list[Observation]:
    """Every reported figure, flattened for basic validation (section 21.1).

    Everything the store holds, including the values a `FactSet` discards when
    it picks a winner. A filing contradicting itself is only visible while both
    of its values are still in view.
    """
    rows = session.execute(
        select(FinancialFact, AnalysisPeriod.code, Filing.provider_filing_id)
        .join(AnalysisPeriod, FinancialFact.period_id == AnalysisPeriod.id)
        .join(Filing, FinancialFact.filing_id == Filing.id)
        .where(
            FinancialFact.company_id == company_id,
            FinancialFact.origin == Origin.REPORTED,
            FinancialFact.value.is_not(None),
            FinancialFact.metric_code.is_not(None),
            FinancialFact.dimensions_hash == "",
        )
    ).all()

    return [
        Observation(
            metric_code=fact.metric_code or "",
            period_code=period_code,
            value=float(fact.value or 0),
            unit=fact.unit,
            filing=reference,
            raw_concept=fact.raw_concept or "",
        )
        for fact, period_code, reference in rows
    ]


def compute(code: str, facts: FactSet, period: FiscalPeriod) -> float | None:
    """One metric in one period, or None when it cannot be computed."""
    spec = CALCULATED_BY_CODE.get(code)
    if spec is None:
        return None
    return spec.compute(facts, period).value


def list_companies(session: Session, *, published_only: bool = True) -> list[Company]:
    """Companies a reader may see, by display name.

    Ingesting and publishing are separate acts. A company can be loaded,
    hand-checked and left invisible, which is what `is_published` is for — so
    the default here is the published set, and anything that wants the whole
    store has to ask for it explicitly.
    """
    statement = select(Company).order_by(Company.display_name)
    if published_only:
        statement = statement.where(Company.is_published)
    return list(session.scalars(statement))


def latest_snapshot(
    session: Session, company_id: uuid.UUID
) -> tuple[AnalysisSnapshotRow, AnalysisPeriod] | None:
    """The most recent **quarter** with a current snapshot.

    Explicitly a quarter, now that full years get snapshots too. A fiscal year
    ends on the same day as its fourth quarter, so ordering by end date alone
    would sometimes open a company on the year and sometimes on the quarter,
    depending on which row the database happened to return first.
    """
    row = session.execute(
        select(AnalysisSnapshotRow, AnalysisPeriod)
        .join(AnalysisPeriod, AnalysisSnapshotRow.period_id == AnalysisPeriod.id)
        .where(
            AnalysisSnapshotRow.company_id == company_id,
            AnalysisSnapshotRow.is_current.is_(True),
            AnalysisPeriod.duration_kind == DurationKind.QUARTER,
        )
        .order_by(AnalysisPeriod.period_end.desc())
        .limit(1)
    ).first()
    return (row[0], row[1]) if row else None


def snapshot_for_period(
    session: Session, company_id: uuid.UUID, period_code: str
) -> tuple[AnalysisSnapshotRow, AnalysisPeriod] | None:
    """The current snapshot for one named period."""
    row = session.execute(
        select(AnalysisSnapshotRow, AnalysisPeriod)
        .join(AnalysisPeriod, AnalysisSnapshotRow.period_id == AnalysisPeriod.id)
        .where(
            AnalysisSnapshotRow.company_id == company_id,
            AnalysisPeriod.code == period_code,
            AnalysisSnapshotRow.is_current.is_(True),
        )
    ).first()
    return (row[0], row[1]) if row else None


def available_periods(session: Session, company_id: uuid.UUID) -> list[str]:
    """Every period with a current snapshot, oldest first.

    Quarters and full years both appear. They are ordered by end date and then
    by kind, so a year sorts after the quarter that closes it rather than
    interleaving unpredictably.
    """
    return list(
        session.scalars(
            select(AnalysisPeriod.code)
            .join(AnalysisSnapshotRow, AnalysisSnapshotRow.period_id == AnalysisPeriod.id)
            .where(
                AnalysisSnapshotRow.company_id == company_id,
                AnalysisSnapshotRow.is_current.is_(True),
            )
            .order_by(AnalysisPeriod.period_end, AnalysisPeriod.duration_kind)
        )
    )


def metric_history(
    session: Session,
    company_id: uuid.UUID,
    metric_code: str,
    duration_kind: DurationKind = DurationKind.QUARTER,
) -> list[tuple[str, float | None]]:
    """One metric across every snapshot of one period kind, oldest first.

    Read from stored snapshots rather than recomputed, so a chart and a report
    page can never disagree (spec section 23).

    **One kind at a time, and quarters by default.** Full years now get
    snapshots too, and a series carrying both would put a twelve-month figure
    next to a three-month one on the same axis — the mixing section 14.6 exists
    to forbid, and it would read as a company that quadrupled and collapsed
    every fourth bar.
    """
    rows = session.execute(
        select(AnalysisPeriod.code, AnalysisSnapshotRow.payload_json)
        .join(AnalysisSnapshotRow, AnalysisSnapshotRow.period_id == AnalysisPeriod.id)
        .where(
            AnalysisSnapshotRow.company_id == company_id,
            AnalysisSnapshotRow.is_current.is_(True),
            AnalysisPeriod.duration_kind == duration_kind,
        )
        .order_by(AnalysisPeriod.period_end)
    ).all()

    history: list[tuple[str, float | None]] = []
    for code, payload in rows:
        metrics = payload.get("metrics", []) if isinstance(payload, dict) else []
        match = next((m for m in metrics if m.get("code") == metric_code), None)
        history.append((code, None if match is None else match.get("value")))
    return history
