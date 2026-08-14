"""Raising watch items, and reviewing them a period later.

The engine does two things and nothing else. It opens an item when a pattern
worth remembering fired, and it re-reads that same metric in a later period to
say whether the move widened, narrowed, stopped or could not be measured.

**It invents no threshold.** "Materially larger" is the one judgement here, and
rather than a new number it reuses `Threshold.minimum_magnitude` — already
defined as the floor below which a move is not worth a sentence. Applied to the
difference between two year-on-year changes it says the same thing about the
same metric in the same units: a collection period that drifted from +14 days to
+14.4 days has not worsened, it has stayed where it was.

Resolution is likewise borrowed rather than invented: an item resolves when the
signal that raised it stops firing, which is the threshold's own account of a
value back in normal range.
"""

from collections.abc import Sequence

from financial_core.patterns.model import Pattern
from financial_core.signals.engine import MetricSeries
from financial_core.signals.model import Signal
from financial_core.signals.thresholds import ThresholdSet
from financial_core.watch.model import WatchItem, WatchObservation, WatchStatus

MESSAGE_KEYS = {
    WatchStatus.OPEN: "watch.opened",
    WatchStatus.IMPROVED: "watch.improved",
    WatchStatus.WORSENED: "watch.worsened",
    WatchStatus.RESOLVED: "watch.resolved",
    WatchStatus.NOT_MEASURABLE: "watch.not_measurable",
}


def _observe(
    metric_code: str,
    period_code: str,
    series: MetricSeries | None,
    deviation: float | None = None,
) -> WatchObservation:
    """Read one metric's level and year-on-year move out of its series."""
    value: float | None = None
    change: float | None = None

    if series is not None:
        latest = series.latest
        value = None if latest is None else latest.value
        changes = series.year_on_year_changes()
        if changes:
            change = changes[-1].value

    return WatchObservation(
        metric_code=metric_code,
        period_code=period_code,
        value=value,
        year_on_year_change=change,
        deviation=deviation,
    )


def open_items(
    company_id: str,
    period_code: str,
    patterns: Sequence[Pattern],
    signals: Sequence[Signal],
    series_by_metric: dict[str, MetricSeries],
) -> list[WatchItem]:
    """Raise a watch item for each concerning pattern in this period.

    A positive pattern raises nothing. Section 28 is about what to check in the
    next report, and "this went well" is not a question the next report answers.

    The item watches the metric behind the pattern's most severe member signal:
    that is the observation carrying the pattern, so it is the one whose
    improvement or worsening actually answers the question.
    """
    by_code = {signal.code: signal for signal in signals}
    items: list[WatchItem] = []

    for pattern in patterns:
        if not pattern.is_concerning:
            continue

        members = [by_code[code] for code in pattern.signal_codes if code in by_code]
        if not members:
            continue

        carrier = max(members, key=lambda s: abs(s.deviation or 0.0))
        items.append(
            WatchItem(
                company_id=company_id,
                source_code=pattern.code,
                opened_in_period=period_code,
                opened_from=_observe(
                    carrier.metric_code,
                    period_code,
                    series_by_metric.get(carrier.metric_code),
                    carrier.deviation,
                ),
                status=WatchStatus.OPEN,
                status_reason=MESSAGE_KEYS[WatchStatus.OPEN],
            )
        )

    return items


def _decide(
    item: WatchItem,
    current: WatchObservation,
    still_firing: bool,
    floor: float,
) -> WatchStatus:
    """What this period says about an item raised earlier."""
    if current.year_on_year_change is None:
        return WatchStatus.NOT_MEASURABLE

    if not still_firing:
        return WatchStatus.RESOLVED

    opened = item.opened_from.year_on_year_change
    if opened is None or opened == 0.0:
        # The item was raised on a move nobody can now compare against. The
        # signal is still firing, so it has not resolved; it simply has no
        # direction to report.
        return WatchStatus.OPEN

    drift = current.year_on_year_change - opened
    if abs(drift) < floor:
        return WatchStatus.OPEN

    # Measured along the direction the item was opened in, not as a bare
    # magnitude. Collection that lengthened 14 days and has now shortened 18 has
    # made a larger move than the one it was raised on, and reading that as a
    # worsening would report an improvement as its opposite.
    moved_further = drift > 0 if opened > 0 else drift < 0
    return WatchStatus.WORSENED if moved_further else WatchStatus.IMPROVED


def review(
    item: WatchItem,
    period_code: str,
    signals: Sequence[Signal],
    series_by_metric: dict[str, MetricSeries],
    thresholds: ThresholdSet,
    sector: str | None = None,
) -> WatchItem:
    """Re-read the item's metric in a later period and update its status.

    A resolved item is returned untouched. Everything else is re-read, including
    an item that was `not_measurable` last time: a gap in the data is a pause,
    and the next period with figures picks the question back up.
    """
    if item.status.is_closed:
        return item

    metric_code = item.opened_from.metric_code
    firing = next((s for s in signals if s.metric_code == metric_code), None)
    current = _observe(
        metric_code,
        period_code,
        series_by_metric.get(metric_code),
        None if firing is None else firing.deviation,
    )

    threshold = thresholds.for_metric(metric_code, sector)
    floor = 0.0 if threshold is None else threshold.minimum_magnitude
    status = _decide(item, current, firing is not None, floor)

    from dataclasses import replace

    return replace(
        item,
        status=status,
        reviewed_in_period=period_code,
        current=current,
        resolved_in_period=period_code if status is WatchStatus.RESOLVED else None,
        status_reason=MESSAGE_KEYS[status],
        history=(*item.history, (period_code, status)),
    )
