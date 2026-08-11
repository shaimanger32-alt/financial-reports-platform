"""Turning a metric's history into observations.

The engine holds no financial opinions. It asks how this period's move compares
with the moves this company normally makes, checks that the move clears the
floor set for the metric, counts how long it has persisted, and reports. Which
metrics matter and how far is far enough are data, in `rules` and `thresholds`.

**Everything is measured on the year-on-year change, not the level.** Comparing
levels across adjacent quarters mistakes seasonality for news: a retailer's
collection period is meant to look different in the fourth quarter, and a
company whose figure swings every quarter has said nothing by swinging again.
Spec section 14.1 makes year on year the default comparison, and differencing
against the same quarter a year earlier removes the seasonal pattern instead of
trying to model it.

Confidence follows spec section 20 exactly: a single period is `LOW`, two or
more consecutive periods is `MEDIUM`, and `HIGH` needs an explanation from the
filing itself — which arrives in phase 6, so this engine never issues it.
"""

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Final

from financial_core.periods import FiscalPeriod
from financial_core.signals.baseline import build_baseline
from financial_core.signals.model import Confidence, Direction, Signal
from financial_core.signals.rules import SignalRule
from financial_core.signals.thresholds import ThresholdSet

QUARTERS_IN_YEAR: Final[int] = 4


@dataclass(frozen=True, slots=True)
class MetricObservation:
    """One metric's value in one period."""

    period: FiscalPeriod
    value: float | None


@dataclass(frozen=True, slots=True)
class MetricSeries:
    """A metric's history for one company, oldest first, one entry per quarter."""

    metric_code: str
    observations: tuple[MetricObservation, ...]

    @property
    def latest(self) -> MetricObservation | None:
        return self.observations[-1] if self.observations else None

    def values(self) -> list[float | None]:
        return [observation.value for observation in self.observations]

    def year_on_year_changes(self) -> list[MetricObservation]:
        """Each period's change against the same quarter a year earlier."""
        changes: list[MetricObservation] = []
        for index in range(QUARTERS_IN_YEAR, len(self.observations)):
            current = self.observations[index]
            prior = self.observations[index - QUARTERS_IN_YEAR]
            if current.value is None or prior.value is None:
                changes.append(MetricObservation(current.period, None))
            else:
                changes.append(MetricObservation(current.period, current.value - prior.value))
        return changes


def _direction_of(change: float) -> Direction:
    if change > 0:
        return Direction.UP
    if change < 0:
        return Direction.DOWN
    return Direction.FLAT


def evaluate_rule(
    rule: SignalRule,
    series: MetricSeries,
    thresholds: ThresholdSet,
    sector: str | None = None,
) -> Signal | None:
    """Raise a signal when this year-on-year move is unlike the company's usual.

    Returns None whenever nothing can be concluded: no value, too little
    history, no threshold defined, a move in the direction the rule does not
    care about, or a move too small to be worth a sentence.
    """
    threshold = thresholds.for_metric(rule.metric_code, sector)
    if threshold is None:
        return None

    changes = series.year_on_year_changes()
    if not changes:
        return None

    latest_change = changes[-1]
    if latest_change.value is None:
        return None

    direction = _direction_of(latest_change.value)
    if direction is not rule.concerning_direction:
        return None

    prior_changes = [change.value for change in changes[:-1] if change.value is not None]
    baseline = build_baseline(prior_changes)
    if baseline is None or not baseline.is_reliable:
        return None

    deviation = baseline.deviation_of(latest_change.value)
    if deviation is None:
        return None

    def departs(change: float) -> bool:
        return (
            _direction_of(change) is rule.concerning_direction
            and abs(change) >= threshold.minimum_magnitude
        )

    persisted = 0
    for change in reversed(changes):
        if change.value is None or not departs(change.value):
            break
        persisted += 1

    if not threshold.is_breached(deviation, latest_change.value, persisted):
        return None

    latest = series.latest
    return Signal(
        code=rule.code,
        period=latest_change.period,
        metric_code=rule.metric_code,
        direction=direction,
        severity=threshold.severity if rule.severity is None else rule.severity,
        confidence=Confidence.MEDIUM if persisted >= 2 else Confidence.LOW,
        rule_version=rule.version,
        value=None if latest is None else latest.value,
        baseline=baseline.median,
        deviation=deviation,
        periods_persisted=persisted,
        message_key=rule.message_key,
        inputs={
            "year_on_year_change": latest_change.value,
            "usual_change": baseline.median,
            "spread": baseline.spread,
        },
    )


def evaluate_all(
    rules: Sequence[SignalRule],
    series_by_metric: dict[str, MetricSeries],
    thresholds: ThresholdSet,
    sector: str | None = None,
) -> list[Signal]:
    """Run every rule that has data, most concerning first."""
    signals = []
    for rule in rules:
        series = series_by_metric.get(rule.metric_code)
        if series is None:
            continue
        signal = evaluate_rule(rule, series, thresholds, sector)
        if signal is not None:
            signals.append(signal)

    order = {"critical": 0, "warning": 1, "watch": 2, "positive": 3, "info": 4}
    return sorted(signals, key=lambda s: (order[s.severity.value], -abs(s.deviation or 0.0)))
