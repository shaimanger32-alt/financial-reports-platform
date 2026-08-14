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

from financial_core.metrics import (
    CALCULATED_BY_CODE,
    DEFAULT_TIERING,
    REPORTED_METRICS,
    FactSet,
    MarketTiering,
    MetricTier,
    compute_all,
)
from financial_core.metrics.formulas import FORMULA_VERSION
from financial_core.patterns import ALL_PATTERNS, PATTERN_VERSION, Pattern, PatternRule
from financial_core.patterns import evaluate_all as evaluate_patterns
from financial_core.periods import FiscalPeriod, PeriodKind, quarter_end
from financial_core.pulse import DIMENSIONS, PULSE_VERSION, PulseDimension, read_pulse
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
from financial_core.validation import IdentityCheck, check_all
from financial_core.watch import WATCH_VERSION, WatchItem, open_items, review

# v2 added patterns. A snapshot now says more than it did, so it is a different
# analysis and gets a different version rather than quietly replacing v1 in
# place (spec section 33).
ANALYSIS_VERSION = "v2"


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
class PatternView:
    """Several observations read as one thing, as a reader sees it.

    Carries the codes of the signals it is made of rather than copies of them.
    A pattern has no content of its own beyond that combination, and listing the
    codes is what lets the page fold those signals underneath it instead of
    saying the same thing twice.
    """

    code: str
    severity: str
    confidence: str
    message_key: str
    rule_version: str
    signal_codes: tuple[str, ...]
    optional_signal_codes: tuple[str, ...]
    explanation_status: str
    independent_signal_count: int = 0
    """Matched signals that are separate observations rather than the same
    arithmetic seen twice. Confidence rests on this, not on the raw count."""
    dependent_signals_counted_once: tuple[str, ...] = ()
    """Matched signals that share their inputs, so a reader of the payload can
    tell corroboration from a restatement of the same figures."""


@dataclass(frozen=True, slots=True)
class IdentityView:
    """One accounting identity, as a reader sees it.

    Spec section 21.2 runs these before analysis. Surfacing the result is the
    point: a figure that does not add up is not a slightly worse figure, and a
    reader is entitled to know which of the checks ran and which held.

    `unreported_terms` is why a broken identity is not an accusation. A cash
    bridge that fails at a company which filed no exchange-rate line is far more
    likely to be our mapping than their accounts.
    """

    name: str
    outcome: str
    expected: float | None
    actual: float | None
    relative_difference: float | None
    missing: tuple[str, ...] = ()
    unreported_terms: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class PulseView:
    """One Report Pulse dimension, as a reader sees it (spec section 6.1).

    Carries the codes of the signals its state was read from. The band is a
    summary of the findings below it and nothing more, so a reader who does not
    believe it can check what it was built from.
    """

    code: str
    state: str
    message_key: str
    signal_codes: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class RestatementView:
    """A figure a later filing reported differently, as a reader sees it.

    Decision 0009 keeps both values and requires the disagreement to be
    **surfaced, never resolved silently**. The engine does now prefer the later
    filing when it calculates, which is right and is exactly why this has to be
    reported: without it a figure changes underneath a reader with nothing said.
    """

    metric_code: str
    superseded_value: float
    current_value: float
    superseded_filing: str
    current_filing: str
    relative_difference: float | None


@dataclass(frozen=True, slots=True)
class SnapshotVersions:
    """Everything that decided what this snapshot says."""

    analysis: str
    metrics: str
    rules: str
    thresholds: str
    mappings: str
    patterns: str
    pulse: str
    tiering: str
    """Which market's tiering decided whether each metric is CORE (decision 0011)."""
    watch: str = WATCH_VERSION
    """The lifecycle rules that decided each watch item's status."""


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
    patterns: tuple[PatternView, ...] = ()
    identities: tuple[IdentityView, ...] = ()
    restatements: tuple[RestatementView, ...] = ()
    pulse: tuple[PulseView, ...] = ()
    watch_items: tuple[WatchItem, ...] = ()
    """What earlier periods asked this one to check, as it stands now.

    Derived rather than accumulated: the whole sequence is rebuilt from the
    stored periods on every run, so a formula or rule change reruns the memory
    with it and `make snapshots` stays idempotent."""

    @property
    def broken_identities(self) -> tuple[IdentityView, ...]:
        return tuple(view for view in self.identities if view.outcome == "broken")

    @property
    def patterned_signal_codes(self) -> frozenset[str]:
        """Signals that some pattern already accounts for."""
        return frozenset(
            code
            for pattern in self.patterns
            for code in (*pattern.signal_codes, *pattern.optional_signal_codes)
        )

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
            "patterns": [asdict(pattern) for pattern in self.patterns],
            "identities": [asdict(identity) for identity in self.identities],
            "restatements": [asdict(item) for item in self.restatements],
            "pulse": [asdict(band) for band in self.pulse],
            "watch_items": [_watch_payload(item) for item in self.watch_items],
        }


def _watch_payload(item: WatchItem) -> dict[str, Any]:
    """A watch item as JSON, with both readings kept side by side.

    The opening reading travels with the current one on purpose: "collection
    lengthened 14 days, and now 22" is the whole content of the item, and a
    payload carrying only the latest figure would leave the page unable to say
    what improved.
    """
    return {
        "source_code": item.source_code,
        "status": item.status.value,
        "status_reason": item.status_reason,
        "opened_in_period": item.opened_in_period,
        "reviewed_in_period": item.reviewed_in_period,
        "resolved_in_period": item.resolved_in_period,
        "metric_code": item.opened_from.metric_code,
        "opened_from": asdict(item.opened_from),
        "current": None if item.current is None else asdict(item.current),
        "history": [
            {"period_code": period, "status": status.value} for period, status in item.history
        ],
    }


def _to_metric_view(code: str, result: Any, tiering: MarketTiering) -> MetricView:
    spec = CALCULATED_BY_CODE[code]
    return MetricView(
        code=code,
        name_he=spec.name_he,
        name_en=spec.name_en,
        category=spec.category.value,
        unit_type=spec.unit_type.value,
        tier=_tier_in(tiering, code, spec.tier),
        value=result.value,
        formula_version=result.formula_version,
        warnings=tuple(warning.value for warning in result.warnings),
        inputs=dict(result.inputs),
        missing_inputs=result.missing_inputs,
    )


def _collect_line_items(
    facts: FactSet, period: FiscalPeriod, tiering: MarketTiering
) -> tuple[LineItemView, ...]:
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
                tier=_tier_in(tiering, spec.code, spec.tier),
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


def _tier_in(tiering: MarketTiering, code: str, catalogue_tier: MetricTier) -> str:
    """The tier this metric holds in the market being read.

    Decision 0011: the tier is a property of the market, not of the formula. The
    current ratio is CORE in Israel and EXTENDED in the United States, because
    11% of American issuers present no current/non-current split at all.
    """
    return tiering.tier_of(code, catalogue_tier).value


def _to_identity_view(check: IdentityCheck) -> IdentityView:
    return IdentityView(
        name=check.name,
        outcome=check.outcome.value,
        expected=check.expected,
        actual=check.actual,
        relative_difference=check.relative_difference,
        missing=check.missing,
        unreported_terms=check.unreported_terms,
    )


def _identity_figures(facts: FactSet, period: FiscalPeriod) -> dict[str, float | None]:
    """The figures the identities need, balances read at the period's close."""
    instant = FiscalPeriod(
        fiscal_year=period.fiscal_year,
        fiscal_quarter=period.fiscal_quarter,
        period_kind=PeriodKind.INSTANT,
        duration_kind=None,
        end=quarter_end(period.fiscal_year, period.fiscal_quarter),
    )
    codes = (
        "total_assets",
        "equity_and_liabilities",
        "current_liabilities",
        "non_current_liabilities",
        "total_equity",
        "revenue",
        "cost_of_sales",
        "gross_profit",
        "operating_cash_flow",
        "investing_cash_flow",
        "financing_cash_flow",
        "net_change_in_cash",
        "effect_of_exchange_rate_on_cash",
    )
    figures: dict[str, float | None] = {}
    for code in codes:
        value = facts.value(code, period)
        figures[code] = facts.value(code, instant) if value is None else value
    return figures


def _to_pattern_view(pattern: Pattern) -> PatternView:
    return PatternView(
        code=pattern.code,
        severity=pattern.severity.value,
        confidence=pattern.confidence.value,
        message_key=pattern.message_key,
        rule_version=pattern.rule_version,
        signal_codes=pattern.signal_codes,
        optional_signal_codes=pattern.optional_signal_codes,
        explanation_status=pattern.explanation_status.value,
        independent_signal_count=pattern.independent_signal_count,
        dependent_signals_counted_once=pattern.dependent_signals_counted_once,
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
    pattern_rules: Sequence[PatternRule] = ALL_PATTERNS,
    tiering: MarketTiering = DEFAULT_TIERING,
    restatements: Sequence[RestatementView] = (),
    dimensions: Sequence[PulseDimension] = DIMENSIONS,
    carried_watch_items: Sequence[WatchItem] = (),
) -> AnalysisSnapshot:
    """Compute everything for one period and package it.

    Metrics that could not be computed are kept rather than dropped. "We do not
    know this, and here is which input was missing" is information a reader is
    entitled to, and silently omitting the row would read as though the metric
    did not exist (spec section 4.4).

    `carried_watch_items` are the items still open coming into this period. They
    are reviewed against it before this period's own patterns raise new ones, so
    a pattern that fires again does not review the item it just opened.
    """
    results = compute_all(facts, period)
    metrics = tuple(_to_metric_view(code, results[code], tiering) for code in sorted(results))

    identities = tuple(
        _to_identity_view(check) for check in check_all(_identity_figures(facts, period))
    )

    available = frozenset(metric.code for metric in metrics if metric.is_available)

    raised = evaluate_all(rules, series_by_metric, thresholds, sector)
    signals = tuple(_to_signal_view(signal) for signal in raised)
    # A pattern whose premise is a fact about the level rather than about how
    # unusual a move was needs the values themselves, not only the signals.
    metric_values = {metric.code: metric.value for metric in metrics}
    found = evaluate_patterns(raised, pattern_rules, sector, metric_values)
    patterns = tuple(_to_pattern_view(pattern) for pattern in found)

    reviewed = [
        review(item, period.code, raised, series_by_metric, thresholds, sector)
        for item in carried_watch_items
    ]
    opened = open_items(company_id, period.code, found, raised, series_by_metric)

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
            patterns=PATTERN_VERSION,
            pulse=PULSE_VERSION,
            tiering=f"{tiering.code}@{tiering.version}",
            watch=WATCH_VERSION,
        ),
        line_items=_collect_line_items(facts, period, tiering),
        metrics=metrics,
        signals=signals,
        patterns=patterns,
        identities=identities,
        restatements=tuple(restatements),
        pulse=tuple(
            PulseView(
                code=reading.code,
                state=reading.state.value,
                message_key=reading.message_key,
                signal_codes=reading.signal_codes,
            )
            for reading in read_pulse(raised, available, dimensions).readings
        ),
        # An item already tracking a metric is not opened a second time because
        # its pattern fired again; the review it just received is the answer.
        watch_items=(
            *reviewed,
            *(
                item
                for item in opened
                if item.source_code not in {carried.source_code for carried in reviewed}
            ),
        ),
    )
