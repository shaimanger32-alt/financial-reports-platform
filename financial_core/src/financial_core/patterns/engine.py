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

from collections.abc import Sequence
from typing import Final

from financial_core.patterns.model import ExplanationStatus, Pattern
from financial_core.patterns.rules import ALL_PATTERNS, PatternRule
from financial_core.periods import FiscalPeriod
from financial_core.signals.model import Confidence, Severity, Signal

_SEVERITY_ORDER: Final[dict[Severity, int]] = {
    Severity.CRITICAL: 0,
    Severity.WARNING: 1,
    Severity.WATCH: 2,
    Severity.POSITIVE: 3,
    Severity.INFO: 4,
}


def _most_severe(signals: Sequence[Signal]) -> Severity:
    return min((signal.severity for signal in signals), key=lambda s: _SEVERITY_ORDER[s])


def evaluate_pattern(
    rule: PatternRule,
    signals: Sequence[Signal],
    sector: str | None = None,
) -> Pattern | None:
    """Report the pattern when enough of its signals fired in this period.

    Returns None whenever the combination is not there: too few of the required
    signals, or none of them persisted long enough. A pattern that half fired is
    not a weaker pattern, it is a set of separate observations, and the signals
    are already shown on their own.
    """
    if sector and rule.sector_scope not in {"general", sector}:
        return None

    by_code = {signal.code: signal for signal in signals}

    # Every prerequisite, or nothing. These carry the premise the wording rests
    # on, so a pattern missing one would describe a company it is not about.
    if any(code not in by_code for code in rule.prerequisite_signals):
        return None

    matched_required = tuple(code for code in rule.required_signals if code in by_code)
    if len(matched_required) < rule.minimum_required:
        return None

    matched_required = (*rule.prerequisite_signals, *matched_required)
    matched_signals = [by_code[code] for code in matched_required]
    if max(signal.periods_persisted for signal in matched_signals) < rule.minimum_periods:
        return None

    matched_optional = tuple(code for code in rule.optional_signals if code in by_code)

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
        # MEDIUM. One signal carrying a pattern on its own is not corroboration,
        # whatever its magnitude, so it stays LOW.
        confidence=Confidence.MEDIUM if len(matched_required) >= 2 else Confidence.LOW,
        rule_version=rule.version,
        message_key=rule.message_key,
        explanation_status=ExplanationStatus.NOT_SEARCHED,
    )


def evaluate_all(
    signals: Sequence[Signal],
    rules: Sequence[PatternRule] = ALL_PATTERNS,
    sector: str | None = None,
) -> list[Pattern]:
    """Run every pattern rule against one period's signals, most severe first."""
    patterns = [
        pattern
        for pattern in (evaluate_pattern(rule, signals, sector) for rule in rules)
        if pattern is not None
    ]
    return sorted(
        patterns,
        key=lambda p: (_SEVERITY_ORDER[p.severity], -len(p.signal_codes)),
    )
