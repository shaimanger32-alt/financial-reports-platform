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
from database.repository import load_fact_set, load_metric_series
from financial_core.analysis import ANALYSIS_VERSION, AnalysisSnapshot, build_snapshot
from financial_core.periods import DurationKind, FiscalPeriod
from financial_core.signals import ALL_RULES, MetricSeries

logger = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class SnapshotReport:
    """What one generation run produced."""

    generated: int
    periods: tuple[str, ...]
    signals: int


def generate_snapshots(
    session: Session,
    company: Company,
    quarters: int = 16,
    mapping_version: str = "v1",
) -> SnapshotReport:
    """Build a snapshot for every discrete quarter the company has data for.

    Only discrete quarters get one. A year-to-date figure and a quarter answer
    different questions, and giving both a snapshot invites a reader to compare
    them (spec section 14.6).
    """
    facts = load_fact_set(session, company.id)
    watched = sorted({rule.metric_code for rule in ALL_RULES})
    series = load_metric_series(session, company.id, watched, quarters=quarters)

    quarter_periods = [
        period
        for period in facts.periods(duration_kind=DurationKind.QUARTER)
        if period.duration_kind is DurationKind.QUARTER
    ]

    rows = {
        row.code: row
        for row in session.scalars(
            select(AnalysisPeriod).where(AnalysisPeriod.company_id == company.id)
        )
    }

    generated: list[str] = []
    total_signals = 0

    for period in sorted(quarter_periods):
        period_row = rows.get(period.code)
        if period_row is None:
            continue

        snapshot = build_snapshot(
            company_id=str(company.id),
            period=period,
            facts=facts,
            series_by_metric=_series_up_to(series, period),
            mapping_version=mapping_version,
            sector=company.sector_name,
        )
        _store(session, company, period_row, snapshot)
        generated.append(period.code)
        total_signals += len(snapshot.signals)

    session.flush()
    return SnapshotReport(generated=len(generated), periods=tuple(generated), signals=total_signals)


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
            payload_json=snapshot.to_payload(),
            is_current=True,
        )
    )


__all__ = ["ANALYSIS_VERSION", "SnapshotReport", "generate_snapshots"]
