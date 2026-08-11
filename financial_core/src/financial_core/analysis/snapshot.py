"""Assembling one period's analysis into a single readable object.

Spec section 23: the work happens once, when a filing arrives, and a page view
reads the result. That keeps responses fast, keeps cost flat as traffic grows,
and — the part that matters most here — makes the answer *reproducible*. Two
readers looking at the same report a month apart see the same numbers, because
they are reading the same stored object rather than re-running an engine that
may have changed underneath them.

Which is why every version travels with the payload. A snapshot that cannot say
which formulas and rules produced it cannot be audited later (section 33).

This module is pure. It takes facts and produces a payload; persisting it is the
database layer's business.
"""

from collections.abc import Sequence
from dataclasses import asdict, dataclass, field
from typing import Any

from financial_core.metrics import CALCULATED_BY_CODE, REPORTED_METRICS, FactSet, compute_all
from financial_core.metrics.formulas import FORMULA_VERSION
from financial_core.periods import FiscalPeriod, PeriodKind, quarter_end
from financial_core.signals import (
    ALL_RULES,
    DEFAULT_THRESHOLDS,
    MetricSeries,
    Signal,
    SignalRule,
    ThresholdSet,
    evaluate_all,
)
from financial_core.signals.rules import RULE_VERSION

ANALYSIS_VERSION = "v1"


@dataclass(frozen=True, slots=True)
class MetricView:
    """One metric as a reader sees it, with everything needed to explain it."""

    code: str
    name_he: str
    name_en: str
    category: str
    unit_type: str
    tier: str
    value: float | None
    formula_version: str
    warnings: tuple[str, ...] = ()
    inputs: dict[str, float | None] = field(default_factory=dict)
    missing_inputs: tuple[str, ...] = ()

    @property
    def is_available(self) -> bool:
        return self.value is not None


@dataclass(frozen=True, slots=True)
class LineItemView:
    """A figure the issuer reported, as opposed to one we computed.

    A page that shows only ratios asks the reader to take the underlying figures
    on trust. Revenue of 1,418.8M and growth of 6.4% are different statements,
    and the first is the one that can be checked against the filing.
    """

    code: str
    name_he: str
    name_en: str
    category: str
    tier: str
    value: float | None
    raw_concept: str | None
    origin: str


@dataclass(frozen=True, slots=True)
class SignalView:
    """One observation as a reader sees it.

    Carries a message key rather than a sentence. The wording lives in the
    presentation layer so that no engine can accidentally assert a cause
    (spec section 42).
    """

    code: str
    metric_code: str
    severity: str
    direction: str
    confidence: str
    message_key: str
    rule_version: str
    value: float | None
    year_on_year_change: float | None
    usual_change: float | None
    deviation: float | None
    periods_persisted: int


@dataclass(frozen=True, slots=True)
class SnapshotVersions:
    """Everything that decided what this snapshot says."""

    analysis: str
    metrics: str
    rules: str
    thresholds: str
    mappings: str


@dataclass(frozen=True, slots=True)
class AnalysisSnapshot:
    """One company, one period, everything computed."""

    company_id: str
    period_code: str
    fiscal_year: int
    fiscal_quarter: int
    versions: SnapshotVersions
    line_items: tuple[LineItemView, ...]
    metrics: tuple[MetricView, ...]
    signals: tuple[SignalView, ...]

    @property
    def available_metrics(self) -> tuple[MetricView, ...]:
        return tuple(metric for metric in self.metrics if metric.is_available)

    def to_payload(self) -> dict[str, Any]:
        """A plain dictionary, ready to store as JSON or serve as an API body."""
        return {
            "company_id": self.company_id,
            "period_code": self.period_code,
            "fiscal_year": self.fiscal_year,
            "fiscal_quarter": self.fiscal_quarter,
            "versions": asdict(self.versions),
            "line_items": [asdict(item) for item in self.line_items],
            "metrics": [asdict(metric) for metric in self.metrics],
            "signals": [asdict(signal) for signal in self.signals],
        }


def _to_metric_view(code: str, result: Any) -> MetricView:
    spec = CALCULATED_BY_CODE[code]
    return MetricView(
        code=code,
        name_he=spec.name_he,
        name_en=spec.name_en,
        category=spec.category.value,
        unit_type=spec.unit_type.value,
        tier=spec.tier.value,
        value=result.value,
        formula_version=result.formula_version,
        warnings=tuple(warning.value for warning in result.warnings),
        inputs=dict(result.inputs),
        missing_inputs=result.missing_inputs,
    )


def _collect_line_items(facts: FactSet, period: FiscalPeriod) -> tuple[LineItemView, ...]:
    """Every reported figure for this period, flows and balances alike.

    Flows are read at the period itself; balances at the instant that closes it.
    Mixing the two is precisely what spec section 11.3 separates them to prevent.
    """
    instant = FiscalPeriod(
        fiscal_year=period.fiscal_year,
        fiscal_quarter=period.fiscal_quarter,
        period_kind=PeriodKind.INSTANT,
        duration_kind=None,
        end=quarter_end(period.fiscal_year, period.fiscal_quarter),
    )

    items: list[LineItemView] = []
    for spec in REPORTED_METRICS:
        point = facts.point(spec.code, period) or facts.point(spec.code, instant)
        items.append(
            LineItemView(
                code=spec.code,
                name_he=spec.name_he,
                name_en=spec.name_en,
                category=spec.category.value,
                tier=spec.tier.value,
                value=None if point is None else point.value,
                raw_concept=None if point is None else point.raw_concept,
                origin="reported" if point is None else point.origin.value,
            )
        )
    return tuple(items)


def _to_signal_view(signal: Signal) -> SignalView:
    return SignalView(
        code=signal.code,
        metric_code=signal.metric_code,
        severity=signal.severity.value,
        direction=signal.direction.value,
        confidence=signal.confidence.value,
        message_key=signal.message_key,
        rule_version=signal.rule_version,
        value=signal.value,
        year_on_year_change=signal.inputs.get("year_on_year_change"),
        usual_change=signal.inputs.get("usual_change"),
        deviation=signal.deviation,
        periods_persisted=signal.periods_persisted,
    )


def build_snapshot(
    company_id: str,
    period: FiscalPeriod,
    facts: FactSet,
    series_by_metric: dict[str, MetricSeries],
    *,
    mapping_version: str = "v1",
    sector: str | None = None,
    rules: Sequence[SignalRule] = ALL_RULES,
    thresholds: ThresholdSet = DEFAULT_THRESHOLDS,
) -> AnalysisSnapshot:
    """Compute everything for one period and package it.

    Metrics that could not be computed are kept rather than dropped. "We do not
    know this, and here is which input was missing" is information a reader is
    entitled to, and silently omitting the row would read as though the metric
    did not exist (spec section 4.4).
    """
    results = compute_all(facts, period)
    metrics = tuple(_to_metric_view(code, results[code]) for code in sorted(results))
    signals = tuple(
        _to_signal_view(signal)
        for signal in evaluate_all(rules, series_by_metric, thresholds, sector)
    )

    return AnalysisSnapshot(
        company_id=company_id,
        period_code=period.code,
        fiscal_year=period.fiscal_year,
        fiscal_quarter=period.fiscal_quarter,
        versions=SnapshotVersions(
            analysis=ANALYSIS_VERSION,
            metrics=FORMULA_VERSION,
            rules=RULE_VERSION,
            thresholds=thresholds.version,
            mappings=mapping_version,
        ),
        line_items=_collect_line_items(facts, period),
        metrics=metrics,
        signals=signals,
    )
