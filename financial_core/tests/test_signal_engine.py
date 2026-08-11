"""The signal engine.

Most of these tests are about the engine staying quiet. Raising a signal is
easy; not raising one when a company is simply behaving as it always has is the
part that decides whether the product is worth reading.
"""

import pytest

from financial_core.metrics.catalogue import MetricTier
from financial_core.periods import discrete_period
from financial_core.signals import (
    ALL_RULES,
    CORE_RULES,
    Confidence,
    Direction,
    MetricObservation,
    MetricSeries,
    Severity,
    SignalRule,
    Threshold,
    ThresholdSet,
    build_baseline,
    evaluate_all,
    evaluate_rule,
)

DSO_RULE = SignalRule(
    "SIG_DSO_DETERIORATION",
    "days_sales_outstanding",
    Direction.UP,
    "signal.dso_deterioration",
)

THRESHOLDS = ThresholdSet(
    (
        Threshold(
            metric_code="days_sales_outstanding",
            deviation=2.0,
            minimum_magnitude=5.0,
            minimum_periods=1,
            severity=Severity.WATCH,
        ),
    )
)


def series(*values: float | None, metric: str = "days_sales_outstanding") -> MetricSeries:
    """Build a series ending in 2024 Q3, one observation per quarter."""
    periods = []
    year, quarter = 2024, 3
    for _ in values:
        periods.append(discrete_period(year, quarter))
        quarter -= 1
        if quarter == 0:
            quarter, year = 4, year - 1
    observations = tuple(
        MetricObservation(period, value)
        for period, value in zip(reversed(periods), values, strict=True)
    )
    return MetricSeries(metric_code=metric, observations=observations)


# -- staying quiet --------------------------------------------------------


def test_a_steady_company_produces_no_signal() -> None:
    """Nothing has happened, so nothing is said."""
    steady = series(50, 51, 49, 50, 51, 50, 49, 51, 50, 51, 49, 50)

    assert evaluate_rule(DSO_RULE, steady, THRESHOLDS) is None


def test_seasonality_is_not_mistaken_for_news() -> None:
    """A retailer's fourth quarter is meant to look different from its third.

    Four years of the same seasonal shape, and the pattern repeating once more
    is not an observation. Comparing levels across adjacent quarters would flag
    every fourth quarter forever.
    """
    seasonal = series(40, 42, 41, 75, 41, 43, 42, 76, 40, 42, 41, 75, 41, 43, 42, 76)

    assert evaluate_rule(DSO_RULE, seasonal, THRESHOLDS) is None


def test_a_move_in_the_direction_the_rule_ignores_is_silent() -> None:
    """Collection getting faster is not a collection warning."""
    improving = series(50, 51, 49, 50, 51, 50, 49, 51, 50, 51, 49, 20)

    assert evaluate_rule(DSO_RULE, improving, THRESHOLDS) is None


def test_a_move_below_the_floor_is_noise() -> None:
    """Statistically unusual and financially irrelevant are different things.

    This company never varies, so half a day is many robust units away — and it
    is still half a day.
    """
    flat_company = series(50.0, 50.0, 50.0, 50.0, 50.1, 50.1, 50.1, 50.1, 50.4, 50.4, 50.4, 50.4)

    assert evaluate_rule(DSO_RULE, flat_company, THRESHOLDS) is None


def test_too_little_history_means_no_judgement() -> None:
    """A year-on-year comparison needs a year, and a baseline of them needs four.

    Two years of data yields four change observations, which is the minimum, so
    anything shorter cannot support a judgement at all.
    """
    assert evaluate_rule(DSO_RULE, series(50, 51, 49, 50, 95), THRESHOLDS) is None
    assert evaluate_rule(DSO_RULE, series(50, 51, 49, 50, 51, 52, 50, 95), THRESHOLDS) is None


def test_a_missing_latest_value_is_not_a_signal() -> None:
    incomplete = series(50, 51, 49, 50, 51, 50, 49, 51, 50, 51, 49, None)

    assert evaluate_rule(DSO_RULE, incomplete, THRESHOLDS) is None


def test_no_threshold_means_no_signal() -> None:
    """An unconfigured metric is silent rather than assuming a default."""
    empty = ThresholdSet(())
    departing = series(50, 51, 49, 50, 51, 50, 49, 51, 50, 51, 49, 95)

    assert evaluate_rule(DSO_RULE, departing, empty) is None


# -- speaking up ----------------------------------------------------------


DEPARTING = series(50, 51, 49, 50, 51, 50, 49, 51, 50, 51, 49, 95)
DEPARTING_TWICE = series(50, 51, 49, 50, 51, 50, 49, 51, 50, 51, 90, 95)


def test_a_real_departure_raises_a_signal() -> None:
    result = evaluate_rule(DSO_RULE, DEPARTING, THRESHOLDS)

    assert result is not None
    assert result.code == "SIG_DSO_DETERIORATION"
    assert result.direction is Direction.UP
    assert result.severity is Severity.WATCH
    assert result.value == 95
    assert result.inputs["year_on_year_change"] == pytest.approx(44.0)
    assert result.deviation is not None and result.deviation > 2.0


def test_one_period_is_low_confidence() -> None:
    """Spec section 20: a single quarter carries low confidence."""
    result = evaluate_rule(DSO_RULE, DEPARTING, THRESHOLDS)

    assert result is not None
    assert result.confidence is Confidence.LOW
    assert result.periods_persisted == 1


def test_two_periods_in_a_row_raise_confidence() -> None:
    result = evaluate_rule(DSO_RULE, DEPARTING_TWICE, THRESHOLDS)

    assert result is not None
    assert result.confidence is Confidence.MEDIUM
    assert result.periods_persisted == 2


def test_the_engine_never_issues_high_confidence() -> None:
    """High confidence needs an explanation from the filing, which arrives in
    phase 6. Numbers alone cannot earn it (spec section 20)."""
    result = evaluate_rule(DSO_RULE, DEPARTING_TWICE, THRESHOLDS)

    assert result is not None
    assert result.confidence is not Confidence.HIGH


def test_persistence_can_be_required() -> None:
    """A threshold can insist a condition hold for more than one quarter."""
    strict = ThresholdSet(
        (
            Threshold(
                metric_code="days_sales_outstanding",
                deviation=2.0,
                minimum_magnitude=5.0,
                minimum_periods=2,
            ),
        )
    )

    assert evaluate_rule(DSO_RULE, DEPARTING, strict) is None
    assert evaluate_rule(DSO_RULE, DEPARTING_TWICE, strict) is not None


# -- baselines ------------------------------------------------------------


def test_changes_are_measured_against_the_same_quarter_last_year() -> None:
    """Not against the quarter before, which is where seasonality hides."""
    changes = series(40, 42, 41, 75, 45, 47, 46, 80).year_on_year_changes()

    assert [c.value for c in changes] == [5, 5, 5, 5]


def test_the_current_change_is_not_part_of_its_own_baseline() -> None:
    """Including it would drag the norm toward the move and mute it."""
    result = evaluate_rule(DSO_RULE, DEPARTING, THRESHOLDS)

    assert result is not None
    assert result.baseline == pytest.approx(0.0, abs=2.0)


def test_a_single_outlier_does_not_move_the_norm() -> None:
    """Median and median absolute deviation, not mean and standard deviation.

    One acquisition would inflate a standard deviation enough to hide every
    move that came after it.
    """
    with_outlier = build_baseline([50, 51, 49, 50, 400])
    without = build_baseline([50, 51, 49, 50])

    assert with_outlier is not None and without is not None
    assert with_outlier.median == pytest.approx(50)
    assert without.median == pytest.approx(50)


def test_a_perfectly_flat_history_does_not_divide_by_zero() -> None:
    baseline = build_baseline([50, 50, 50, 50])

    assert baseline is not None
    assert baseline.deviation_of(50) == 0.0
    assert baseline.deviation_of(95) is None


# -- ordering and the rule set --------------------------------------------


def test_signals_come_back_most_concerning_first() -> None:
    rules = (
        DSO_RULE,
        SignalRule(
            "SIG_X", "current_ratio", Direction.DOWN, "signal.x", severity=Severity.CRITICAL
        ),
    )
    thresholds = ThresholdSet(
        (
            Threshold("days_sales_outstanding", deviation=2.0, minimum_magnitude=5.0),
            Threshold("current_ratio", deviation=2.0, minimum_magnitude=0.1),
        )
    )
    data = {
        "days_sales_outstanding": DEPARTING,
        "current_ratio": series(
            1.5,
            1.52,
            1.48,
            1.5,
            1.51,
            1.49,
            1.5,
            1.52,
            1.5,
            1.51,
            1.49,
            0.9,
            metric="current_ratio",
        ),
    }

    signals = evaluate_all(rules, data, thresholds)

    assert [s.severity for s in signals] == [Severity.CRITICAL, Severity.WATCH]


def test_every_rule_carries_a_message_key_and_no_wording() -> None:
    """Section 42: the engine holds no sentences, so it cannot assert a cause."""
    for rule in ALL_RULES:
        assert rule.message_key.startswith("signal.")
        assert rule.version


def test_core_rules_only_watch_core_metrics() -> None:
    """A core rule must fire for any company, so its metric has to be universal."""
    from financial_core.metrics import CALCULATED_BY_CODE

    for rule in CORE_RULES:
        spec = CALCULATED_BY_CODE.get(rule.metric_code)
        assert spec is not None, f"{rule.code} watches an unknown metric"
        assert spec.tier is MetricTier.CORE, f"{rule.code} is core but its metric is not"


def test_rule_codes_are_unique() -> None:
    codes = [rule.code for rule in ALL_RULES]

    assert len(codes) == len(set(codes))
