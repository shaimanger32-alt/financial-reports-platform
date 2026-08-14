"""Generating and storing analysis snapshots.

Spec section 23: computed once when a filing arrives, read many times by page
views. Regeneration replaces the current snapshot rather than editing it, so the
superseded one stays available and "what did this look like under the old rules"
remains answerable (section 33).
"""

import logging
from dataclasses import dataclass

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from database.models import AnalysisPeriod, Company
from database.models import AnalysisSnapshot as AnalysisSnapshotRow
from database.repository import (
    load_annual_metric_series,
    load_fact_set,
    load_metric_series,
    restatements,
)
from financial_core.analysis import (
    ANALYSIS_VERSION,
    AnalysisSnapshot,
    RestatementView,
    build_snapshot,
)
from financial_core.metrics import DEFAULT_TIERING, TIERINGS_BY_CODE
from financial_core.periods import DurationKind, FiscalPeriod
from financial_core.signals import ALL_RULES, MetricSeries
from financial_core.watch import WatchItem

logger = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class SnapshotReport:
    """What one generation run produced."""

    generated: int
    periods: tuple[str, ...]
    signals: int
    patterns: int = 0
    watch_items: int = 0
    annual: int = 0
    restatements: int = 0


def generate_snapshots(
    session: Session,
    company: Company,
    quarters: int = 16,
    mapping_version: str = "v1",
) -> SnapshotReport:
    """Build a snapshot for every discrete quarter and every full fiscal year.

    Year-to-date windows deliberately get none. A nine-month figure and a
    quarter answer different questions, and giving both a snapshot invites a
    reader to compare them (spec section 14.6). A full year is a different
    matter: it is a complete, self-contained period a reader genuinely wants.

    The two are kept strictly apart. An annual snapshot is built from an annual
    series, where "the same period a year earlier" is the previous year rather
    than four entries back — passing the quarterly series would compare a year
    against a quarter and produce a confident, meaningless number.
    """
    facts = load_fact_set(session, company.id)
    watched = sorted({rule.metric_code for rule in ALL_RULES})
    series = load_metric_series(session, company.id, watched, quarters=quarters)
    annual_series = load_annual_metric_series(session, company.id, watched)
    # Decision 0009: a disagreement between two of a company's own filings is
    # surfaced, never resolved silently. The engine prefers the later value; the
    # reader is told that it did.
    restated = restatements(session, company.id, provider=company.provider)

    quarter_periods = [
        period
        for period in facts.periods(duration_kind=DurationKind.QUARTER)
        if period.duration_kind is DurationKind.QUARTER
    ]
    annual_periods = [
        period
        for period in facts.periods(duration_kind=DurationKind.ANNUAL)
        if period.duration_kind is DurationKind.ANNUAL
    ]

    rows = {
        row.code: row
        for row in session.scalars(
            select(AnalysisPeriod).where(AnalysisPeriod.company_id == company.id)
        )
    }

    generated: list[str] = []
    total_signals = 0
    total_patterns = 0
    total_annual = 0
    total_restatements = 0
    total_watch = 0

    # Report memory is derived, not accumulated: the sequence is replayed from
    # the stored periods on every run, so a formula or rule change reruns the
    # memory with it. Quarterly and annual items are carried on separate tracks —
    # a quarter cannot answer a question an annual report asked (section 21.4).
    carried: dict[bool, tuple[WatchItem, ...]] = {True: (), False: ()}

    for period in sorted(quarter_periods + annual_periods):
        period_row = rows.get(period.code)
        if period_row is None:
            continue

        is_annual = period.duration_kind is DurationKind.ANNUAL
        source = annual_series if is_annual else series

        snapshot = build_snapshot(
            company_id=str(company.id),
            period=period,
            facts=facts,
            series_by_metric=_series_up_to(source, period),
            mapping_version=mapping_version,
            sector=company.sector_name,
            # Decision 0011: whether a metric is CORE depends on the market the
            # company reports in. The current ratio is CORE in Israel and
            # EXTENDED in the United States, where 11% of issuers present no
            # current asset split at all.
            tiering=TIERINGS_BY_CODE.get(company.market, DEFAULT_TIERING),
            restatements=[
                RestatementView(
                    metric_code=item.metric_code,
                    superseded_value=item.superseded_value,
                    current_value=item.current_value,
                    superseded_filing=item.superseded_filing,
                    current_filing=item.current_filing,
                    relative_difference=item.relative_difference,
                )
                for item in restated.get(period.code, ())
            ],
            carried_watch_items=carried[is_annual],
        )
        _store(session, company, period_row, snapshot)
        generated.append(period.code)
        if is_annual:
            total_annual += 1
        total_restatements += len(snapshot.restatements)
        total_signals += len(snapshot.signals)
        total_patterns += len(snapshot.patterns)
        total_watch += len(snapshot.watch_items)

        # A resolved item has been answered and stops travelling. Everything
        # else, `not_measurable` included, is still open business.
        carried[is_annual] = tuple(item for item in snapshot.watch_items if item.is_open_business)

    session.flush()
    return SnapshotReport(
        generated=len(generated),
        periods=tuple(generated),
        signals=total_signals,
        patterns=total_patterns,
        watch_items=total_watch,
        annual=total_annual,
        restatements=total_restatements,
    )


def _series_up_to(series: dict[str, MetricSeries], period: FiscalPeriod) -> dict[str, MetricSeries]:
    """Trim every series so it ends at `period`.

    A snapshot for an earlier quarter must not see later data. Otherwise a
    signal would be raised on information that did not exist when that report
    was published, which is not analysis but hindsight.
    """
    trimmed: dict[str, MetricSeries] = {}
    for code, metric_series in series.items():
        observations = tuple(
            observation
            for observation in metric_series.observations
            if observation.period <= period
        )
        trimmed[code] = MetricSeries(metric_code=code, observations=observations)
    return trimmed


def _store(
    session: Session,
    company: Company,
    period_row: AnalysisPeriod,
    snapshot: AnalysisSnapshot,
) -> None:
    """Replace the current snapshot for this company, period and version."""
    versions = snapshot.versions

    existing = session.scalar(
        select(AnalysisSnapshotRow).where(
            AnalysisSnapshotRow.company_id == company.id,
            AnalysisSnapshotRow.period_id == period_row.id,
            AnalysisSnapshotRow.analysis_version == versions.analysis,
        )
    )
    if existing is not None:
        existing.payload_json = snapshot.to_payload()
        existing.metrics_version = versions.metrics
        existing.rules_version = versions.rules
        existing.thresholds_version = versions.thresholds
        existing.mappings_version = versions.mappings
        existing.patterns_version = versions.patterns
        existing.is_current = True
        return

    session.execute(
        update(AnalysisSnapshotRow)
        .where(
            AnalysisSnapshotRow.company_id == company.id,
            AnalysisSnapshotRow.period_id == period_row.id,
        )
        .values(is_current=False)
    )
    session.add(
        AnalysisSnapshotRow(
            company_id=company.id,
            period_id=period_row.id,
            analysis_version=versions.analysis,
            metrics_version=versions.metrics,
            rules_version=versions.rules,
            thresholds_version=versions.thresholds,
            mappings_version=versions.mappings,
            patterns_version=versions.patterns,
            payload_json=snapshot.to_payload(),
            is_current=True,
        )
    )


__all__ = ["ANALYSIS_VERSION", "SnapshotReport", "generate_snapshots"]
