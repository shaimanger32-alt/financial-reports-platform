"""The pattern engine.

As with the signal engine, most of these tests are about staying quiet. A
pattern that fires whenever two unrelated things happened in the same quarter is
noise wearing the costume of insight, so the cases below spend more effort on
what must *not* group than on what must.

The fixtures use Hilan's real 2025-Q4 figures. A pattern engine validated only
against invented numbers proves that the code runs, not that it recognises
anything.
"""

import pytest

from financial_core.metrics.catalogue import MetricTier
from financial_core.patterns import (
    ALL_PATTERNS,
    CORE_PATTERNS,
    PATTERNS_BY_CODE,
    ExplanationStatus,
    PatternRule,
    evaluate_all,
    evaluate_pattern,
)
from financial_core.periods import discrete_period
from financial_core.signals import Confidence, Direction, Severity, Signal

PERIOD = discrete_period(2025, 4)

P1 = PATTERNS_BY_CODE["P1_GROWTH_QUALITY"]
P2 = PATTERNS_BY_CODE["P2_EARNINGS_QUALITY"]


def _every_signal_named_by(rule: PatternRule) -> tuple[str, ...]:
    return (*rule.prerequisite_signals, *rule.required_signals, *rule.optional_signals)


def signal(
    code: str,
    metric_code: str = "cash_conversion",
    *,
    severity: Severity = Severity.WATCH,
    direction: Direction = Direction.DOWN,
    persisted: int = 1,
) -> Signal:
    return Signal(
        code=code,
        period=PERIOD,
        metric_code=metric_code,
        direction=direction,
        severity=severity,
        confidence=Confidence.LOW,
        rule_version="v1",
        periods_persisted=persisted,
    )


# Hilan, 2025-Q4, as the signal engine actually raised them.
HILAN_CASH_DIVERGENCE = Signal(
    code="SIG_EARNINGS_CASH_DIVERGENCE",
    period=PERIOD,
    metric_code="cash_conversion",
    direction=Direction.DOWN,
    severity=Severity.WATCH,
    confidence=Confidence.LOW,
    rule_version="v1",
    value=1.443712868837797,
    baseline=0.1684814926490773,
    deviation=-4.386639175616867,
    periods_persisted=1,
    message_key="signal.earnings_cash_divergence",
)

HILAN_ACCRUALS = Signal(
    code="SIG_ACCRUALS_ELEVATED",
    period=PERIOD,
    metric_code="accruals_proxy",
    direction=Direction.UP,
    severity=Severity.WATCH,
    confidence=Confidence.LOW,
    rule_version="v1",
    value=-0.04105745864311343,
    baseline=-0.0162437938383327,
    deviation=4.36084685448526,
    periods_persisted=1,
    message_key="signal.accruals_elevated",
)


class TestTheCaseItWasWrittenFor:
    """Hilan 2025-Q4: two signals that are two views of one thing."""

    def test_p2_fires_on_hilan(self) -> None:
        pattern = evaluate_pattern(P2, [HILAN_CASH_DIVERGENCE, HILAN_ACCRUALS])

        assert pattern is not None
        assert pattern.code == "P2_EARNINGS_QUALITY"
        assert pattern.signal_codes == (
            "SIG_EARNINGS_CASH_DIVERGENCE",
            "SIG_ACCRUALS_ELEVATED",
        )

    def test_two_independent_signals_earn_medium_confidence(self) -> None:
        """Spec section 20: several metrics pointing the same way is MEDIUM."""
        pattern = evaluate_pattern(P2, [HILAN_CASH_DIVERGENCE, HILAN_ACCRUALS])

        assert pattern is not None
        assert pattern.confidence is Confidence.MEDIUM

    def test_the_pattern_is_no_more_severe_than_what_it_is_made_of(self) -> None:
        pattern = evaluate_pattern(P2, [HILAN_CASH_DIVERGENCE, HILAN_ACCRUALS])

        assert pattern is not None
        assert pattern.severity is Severity.WATCH

    def test_the_pattern_says_nobody_has_read_the_filing(self) -> None:
        """Until phase 6 there is no evidence, and no is not the same as none."""
        pattern = evaluate_pattern(P2, [HILAN_CASH_DIVERGENCE, HILAN_ACCRUALS])

        assert pattern is not None
        assert pattern.explanation_status is ExplanationStatus.NOT_SEARCHED


class TestGrowthQuality:
    """ONE Software 2025-Q2: revenue grew, and collection lengthened with it."""

    ONE_SIGNALS = (
        signal("SIG_REVENUE_ACCELERATION", "revenue_growth_yoy", severity=Severity.POSITIVE),
        signal("SIG_DSO_DETERIORATION", "days_sales_outstanding", direction=Direction.UP),
        signal("SIG_RECEIVABLES_GROWTH_GAP", "receivables_growth_gap", direction=Direction.UP),
    )

    def test_p1_fires_on_one_software(self) -> None:
        pattern = evaluate_pattern(P1, list(self.ONE_SIGNALS))

        assert pattern is not None
        assert pattern.signal_codes == (
            "SIG_REVENUE_ACCELERATION",
            "SIG_DSO_DETERIORATION",
            "SIG_RECEIVABLES_GROWTH_GAP",
        )
        assert pattern.confidence is Confidence.MEDIUM

    def test_growth_alone_is_not_a_warning(self) -> None:
        """A company that simply grew has not earned a quality warning."""
        assert evaluate_pattern(P1, [self.ONE_SIGNALS[0]]) is None

    def test_concerns_without_growth_are_not_a_growth_pattern(self) -> None:
        """Electra 2025-Q3 has both quality concerns and no revenue signal. P1's
        wording says revenue grew, so firing here would state something the
        numbers did not observe."""
        electra = [self.ONE_SIGNALS[1], self.ONE_SIGNALS[2]]

        assert evaluate_pattern(P1, electra) is None
        assert evaluate_all(electra) == []

    def test_one_concern_is_enough(self) -> None:
        """Section 16's own output reads 'הגבייה התארכה ו/או המרווח נשחק'."""
        pattern = evaluate_pattern(P1, [self.ONE_SIGNALS[0], self.ONE_SIGNALS[1]])

        assert pattern is not None
        assert pattern.signal_codes == ("SIG_REVENUE_ACCELERATION", "SIG_DSO_DETERIORATION")

    def test_a_positive_prerequisite_does_not_soften_the_pattern(self) -> None:
        """Revenue acceleration is a positive signal. The pattern is still a
        warning, because the concern is what the pattern is about."""
        pattern = evaluate_pattern(P1, list(self.ONE_SIGNALS))

        assert pattern is not None
        assert pattern.severity is Severity.WATCH


class TestStayingQuiet:
    def test_one_signal_is_not_a_pattern(self) -> None:
        assert evaluate_pattern(P2, [HILAN_CASH_DIVERGENCE]) is None

    def test_no_signals_is_not_a_pattern(self) -> None:
        assert evaluate_pattern(P2, []) is None

    def test_unrelated_signals_in_the_same_quarter_do_not_group(self) -> None:
        """The thing that separates a pattern from a coincidence."""
        signals = [
            signal("SIG_DSO_DETERIORATION", "days_sales_outstanding"),
            signal("SIG_LEVERAGE_INCREASE", "liabilities_to_equity"),
            signal("SIG_MARGIN_EXPANSION", "operating_margin", severity=Severity.POSITIVE),
        ]

        assert evaluate_all(signals) == []

    def test_an_optional_signal_cannot_carry_a_pattern_alone(self) -> None:
        """Corroboration is not evidence. SIG_PROFIT_ACCELERATION is optional to
        P2, and profit rising on its own says nothing about cash."""
        signals = [signal("SIG_PROFIT_ACCELERATION", severity=Severity.POSITIVE)]

        assert evaluate_all(signals) == []

    def test_a_pattern_needing_more_persistence_stays_quiet_on_one_quarter(self) -> None:
        rule = PatternRule(
            code="P_TEST",
            required_signals=("SIG_EARNINGS_CASH_DIVERGENCE", "SIG_ACCRUALS_ELEVATED"),
            minimum_required=2,
            message_key="pattern.test",
            minimum_periods=2,
        )

        assert evaluate_pattern(rule, [HILAN_CASH_DIVERGENCE, HILAN_ACCRUALS]) is None

    def test_a_rule_out_of_sector_scope_stays_quiet(self) -> None:
        rule = PatternRule(
            code="P_RETAIL_ONLY",
            required_signals=("SIG_EARNINGS_CASH_DIVERGENCE", "SIG_ACCRUALS_ELEVATED"),
            minimum_required=2,
            message_key="pattern.test",
            sector_scope="retail",
        )

        assert evaluate_pattern(rule, [HILAN_CASH_DIVERGENCE, HILAN_ACCRUALS], "טכנולוגיה") is None
        assert evaluate_pattern(rule, [HILAN_CASH_DIVERGENCE, HILAN_ACCRUALS], "retail") is not None


class TestWhatThePatternCarries:
    def test_optional_signals_are_recorded_but_kept_apart(self) -> None:
        signals = [
            HILAN_CASH_DIVERGENCE,
            HILAN_ACCRUALS,
            signal("SIG_PROFIT_ACCELERATION", "net_income_growth_yoy", severity=Severity.POSITIVE),
        ]
        pattern = evaluate_pattern(P2, signals)

        assert pattern is not None
        assert pattern.optional_signal_codes == ("SIG_PROFIT_ACCELERATION",)
        assert "SIG_PROFIT_ACCELERATION" not in pattern.signal_codes
        assert len(pattern.all_signal_codes) == 3

    def test_the_engine_never_issues_high_confidence(self) -> None:
        """Section 20 reserves HIGH for an explanation from the filing, which
        arrives with the evidence engine in phase 6."""
        signals = [
            HILAN_CASH_DIVERGENCE,
            HILAN_ACCRUALS,
            signal("SIG_OPERATING_CASH_DETERIORATION", "operating_cash_flow_growth_yoy"),
        ]
        pattern = evaluate_pattern(P2, signals)

        assert pattern is not None
        assert pattern.confidence is not Confidence.HIGH

    def test_patterns_are_ordered_most_severe_first(self) -> None:
        critical = PatternRule(
            code="P_CRITICAL",
            required_signals=("SIG_EARNINGS_CASH_DIVERGENCE", "SIG_ACCRUALS_ELEVATED"),
            minimum_required=2,
            message_key="pattern.test",
            severity=Severity.CRITICAL,
        )
        patterns = evaluate_all([HILAN_CASH_DIVERGENCE, HILAN_ACCRUALS], (P2, critical))

        assert [p.code for p in patterns] == ["P_CRITICAL", "P2_EARNINGS_QUALITY"]


class TestTheRulesAreData:
    def test_no_rule_carries_a_sentence(self) -> None:
        """Section 42 is enforceable only while the engine holds no wording."""
        for rule in ALL_PATTERNS:
            assert rule.message_key.startswith("pattern.")
            assert " " not in rule.message_key

    def test_every_rule_is_versioned(self) -> None:
        for rule in ALL_PATTERNS:
            assert rule.version

    def test_a_rule_cannot_require_more_signals_than_it_names(self) -> None:
        for rule in ALL_PATTERNS:
            assert 1 <= rule.minimum_required <= len(rule.required_signals)

    def test_every_named_signal_exists(self) -> None:
        """A typo in a rule would otherwise make a pattern silently unreachable."""
        from financial_core.signals import RULES_BY_CODE

        for rule in ALL_PATTERNS:
            for code in _every_signal_named_by(rule):
                assert code in RULES_BY_CODE, f"{rule.code} names unknown signal {code}"

    def test_a_core_pattern_rests_only_on_core_signals(self) -> None:
        """Decision 0010: a CORE pattern must work for every company, which it
        cannot do if any input is a metric only some issuers tag."""
        from financial_core.signals import RULES_BY_CODE

        for rule in CORE_PATTERNS:
            assert rule.tier is MetricTier.CORE
            for code in _every_signal_named_by(rule):
                assert RULES_BY_CODE[code].is_core, f"{rule.code} rests on extended {code}"

    def test_no_signal_is_named_twice_by_one_rule(self) -> None:
        for rule in ALL_PATTERNS:
            named = _every_signal_named_by(rule)
            assert len(named) == len(set(named)), f"{rule.code} names a signal twice"

    def test_pattern_codes_are_unique(self) -> None:
        codes = [rule.code for rule in ALL_PATTERNS]
        assert len(codes) == len(set(codes))


@pytest.mark.parametrize("rule", ALL_PATTERNS, ids=lambda r: r.code)
def test_a_rule_never_invents_severity_above_its_signals(rule: PatternRule) -> None:
    """A pattern may be no louder than the observations underneath it."""
    assert rule.severity is None or rule.severity is not Severity.CRITICAL
