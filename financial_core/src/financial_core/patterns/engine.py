"""The pattern engine.

It does one thing: takes the signals already raised for a period and reports
which combinations of them a rule recognises. It reads no facts, computes no
metrics and reaches no conclusion the signals had not already reached
separately.

That narrowness is the point. Section 42 forbids claiming a cause without an
explicit quote from the filing, and an engine that only ever groups existing
observations has no mechanism for inventing one.

Confidence follows spec section 20 as the signal engine does. Two independent
signals pointing the same way is `MEDIUM` — that clause of section 20 describes
a pattern exactly. `HIGH` needs an explanation from the filing, which arrives
with the evidence engine in phase 6, so this engine never issues it.
"""

from collections.abc import Mapping, Sequence
from typing import Final

from financial_core.patterns.model import ExplanationStatus, Pattern
from financial_core.patterns.rules import ALL_PATTERNS, PatternRule
from financial_core.periods import FiscalPeriod
from financial_core.signals.model import Confidence, Severity, Signal

MetricValues = Mapping[str, float | None]

_SEVERITY_ORDER: Final[dict[Severity, int]] = {
    Severity.CRITICAL: 0,
    Severity.WARNING: 1,
    Severity.WATCH: 2,
    Severity.POSITIVE: 3,
    Severity.INFO: 4,
}


def _most_severe(signals: Sequence[Signal]) -> Severity:
    return min((signal.severity for signal in signals), key=lambda s: _SEVERITY_ORDER[s])


def _independent_evidence(rule: PatternRule, matched: Sequence[str]) -> tuple[int, tuple[str, ...]]:
    """How many of the matched signals are independent, and which leaned together.

    Signals derived from the same inputs move together as arithmetic, not as two
    findings. Each declared group collapses to one for the count, and the groups
    that actually contributed more than one member are named so the payload can
    say so (spec section 20).
    """
    remaining = set(matched)
    leaned: list[str] = []
    independent = 0

    for group in rule.dependent_signal_groups:
        members = sorted(remaining & group)
        if not members:
            continue
        remaining -= set(members)
        independent += 1
        if len(members) > 1:
            leaned.append(" + ".join(members))

    return independent + len(remaining), tuple(leaned)


def evaluate_pattern(
    rule: PatternRule,
    signals: Sequence[Signal],
    sector: str | None = None,
    metrics: MetricValues | None = None,
) -> Pattern | None:
    """Report the pattern when enough of its signals fired in this period.

    Returns None whenever the combination is not there: a premise that does not
    hold, too few of the required signals, or none of them persisted long enough.
    A pattern that half fired is not a weaker pattern, it is a set of separate
    observations, and the signals are already shown on their own.
    """
    if sector and rule.sector_scope not in {"general", sector}:
        return None

    by_code = {signal.code: signal for signal in signals}
    values: MetricValues = metrics or {}

    # Every prerequisite, or nothing. These carry the premise the wording rests
    # on, so a pattern missing one would describe a company it is not about.
    if any(code not in by_code for code in rule.prerequisite_signals):
        return None

    # A metric premise the caller supplied no metrics for is unproven, not true.
    if any(
        not condition.is_met_by(values.get(condition.metric_code))
        for condition in rule.prerequisite_metrics
    ):
        return None

    matched_required = tuple(code for code in rule.required_signals if code in by_code)
    if len(matched_required) < rule.minimum_required:
        return None

    matched_required = (*rule.prerequisite_signals, *matched_required)
    matched_signals = [by_code[code] for code in matched_required]
    if max(signal.periods_persisted for signal in matched_signals) < rule.minimum_periods:
        return None

    matched_optional = tuple(code for code in rule.optional_signals if code in by_code)

    independent, leaned_on = _independent_evidence(rule, matched_required)

    message_key = rule.message_key
    for condition, variant in rule.variant_message_keys:
        if condition.is_met_by(values.get(condition.metric_code)):
            message_key = variant
            break

    # Every member signal is about the same period by construction: the signal
    # engine raises one signal per rule for the period being analysed.
    period: FiscalPeriod = matched_signals[0].period

    return Pattern(
        code=rule.code,
        period=period,
        signal_codes=matched_required,
        optional_signal_codes=matched_optional,
        severity=rule.severity or _most_severe(matched_signals),
        # Section 20: several independent metrics pointing the same way is
        # MEDIUM. Signals that restate the same arithmetic are one observation,
        # so they cannot carry a pattern past LOW however many of them fired.
        confidence=Confidence.MEDIUM if independent >= 2 else Confidence.LOW,
        rule_version=rule.version,
        message_key=message_key,
        explanation_status=ExplanationStatus.NOT_SEARCHED,
        independent_signal_count=independent,
        dependent_signals_counted_once=leaned_on,
    )


def evaluate_all(
    signals: Sequence[Signal],
    rules: Sequence[PatternRule] = ALL_PATTERNS,
    sector: str | None = None,
    metrics: MetricValues | None = None,
) -> list[Pattern]:
    """Run every pattern rule against one period's signals, most severe first."""
    patterns = [
        pattern
        for pattern in (evaluate_pattern(rule, signals, sector, metrics) for rule in rules)
        if pattern is not None
    ]
    return sorted(
        patterns,
        key=lambda p: (_SEVERITY_ORDER[p.severity], -len(p.signal_codes)),
    )
