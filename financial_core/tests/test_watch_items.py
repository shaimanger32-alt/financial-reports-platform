"""Report memory across periods.

Most of these are about the two ways a watch item can lie. It can close itself
because the metric went null, which turns missing data into good news; or it can
flip status on a move too small to mean anything, which turns rounding into a
story. Both are worse than having no memory at all, so they get the most cases.
"""

from financial_core.patterns.model import ExplanationStatus, Pattern
from financial_core.periods import discrete_period
from financial_core.signals import Confidence, Direction, Severity, Signal
from financial_core.signals.engine import MetricObservation, MetricSeries
from financial_core.signals.thresholds import Threshold, ThresholdSet
from financial_core.watch import WatchItem, WatchStatus, open_items, review
from financial_core.watch.model import WatchObservation

Q3 = discrete_period(2025, 3)
Q4 = discrete_period(2025, 4)

# A collection period that has to move at least two days to be worth a sentence.
THRESHOLDS = ThresholdSet(
    (Threshold(metric_code="days_sales_outstanding", deviation=2.0, minimum_magnitude=2.0),)
)


def series(*values: float | None, metric: str = "days_sales_outstanding") -> MetricSeries:
    """A five-year quarterly series, oldest first, one observation a year apart."""
    periods = [discrete_period(2021 + index, 3) for index in range(len(values))]
    return MetricSeries(
        metric_code=metric,
        observations=tuple(
            MetricObservation(period, value) for period, value in zip(periods, values, strict=True)
        ),
        periods_per_year=1,
    )


def dso_signal(deviation: float = 3.0) -> Signal:
    return Signal(
        code="SIG_DSO_DETERIORATION",
        period=Q4,
        metric_code="days_sales_outstanding",
        direction=Direction.UP,
        severity=Severity.WATCH,
        confidence=Confidence.LOW,
        rule_version="v1",
        deviation=deviation,
        periods_persisted=1,
    )


def pattern(severity: Severity = Severity.WATCH) -> Pattern:
    return Pattern(
        code="P1_GROWTH_QUALITY",
        period=Q3,
        signal_codes=("SIG_DSO_DETERIORATION",),
        severity=severity,
        confidence=Confidence.LOW,
        rule_version="v1",
        message_key="pattern.growth_quality",
        explanation_status=ExplanationStatus.NOT_SEARCHED,
    )


def opened(change_when_opened: float) -> WatchItem:
    """An item raised on a year-on-year move of `change_when_opened` days."""
    return WatchItem(
        company_id="c1",
        source_code="P1_GROWTH_QUALITY",
        opened_in_period="2025-Q3",
        opened_from=WatchObservation(
            metric_code="days_sales_outstanding",
            period_code="2025-Q3",
            value=54.0,
            year_on_year_change=change_when_opened,
            deviation=3.0,
        ),
    )


class TestRaisingAnItem:
    def test_a_concerning_pattern_opens_one(self) -> None:
        items = open_items(
            "c1",
            "2025-Q3",
            [pattern()],
            [dso_signal()],
            {"days_sales_outstanding": series(40.0, 54.0)},
        )

        assert len(items) == 1
        assert items[0].status is WatchStatus.OPEN
        assert items[0].source_code == "P1_GROWTH_QUALITY"
        assert items[0].opened_from.metric_code == "days_sales_outstanding"

    def test_a_positive_pattern_opens_nothing(self) -> None:
        """Section 28 asks what to check next quarter. "This went well" is not
        a question the next report answers."""
        items = open_items(
            "c1",
            "2025-Q3",
            [pattern(Severity.POSITIVE)],
            [dso_signal()],
            {"days_sales_outstanding": series(40.0, 54.0)},
        )

        assert items == []

    def test_the_item_remembers_the_move_it_was_opened_on(self) -> None:
        items = open_items(
            "c1",
            "2025-Q3",
            [pattern()],
            [dso_signal()],
            {"days_sales_outstanding": series(40.0, 54.0)},
        )

        assert items[0].opened_from.year_on_year_change == 14.0
        assert items[0].opened_from.value == 54.0


class TestTheLifecycle:
    def test_a_widening_move_worsens(self) -> None:
        item = review(
            opened(14.0),
            "2025-Q4",
            [dso_signal()],
            {"days_sales_outstanding": series(40.0, 54.0, 76.0)},
            THRESHOLDS,
        )

        assert item.status is WatchStatus.WORSENED
        assert item.status_reason == "watch.worsened"

    def test_a_narrowing_move_improves(self) -> None:
        item = review(
            opened(14.0),
            "2025-Q4",
            [dso_signal()],
            {"days_sales_outstanding": series(40.0, 54.0, 58.0)},
            THRESHOLDS,
        )

        assert item.status is WatchStatus.IMPROVED

    def test_a_reversal_is_an_improvement_not_a_bigger_move(self) -> None:
        """Collection that lengthened 14 days and has now shortened 18 has moved
        further than it was raised on. Comparing bare magnitudes would report
        that recovery as a worsening."""
        item = review(
            opened(14.0),
            "2025-Q4",
            [dso_signal()],
            {"days_sales_outstanding": series(40.0, 54.0, 76.0, 58.0)},
            THRESHOLDS,
        )

        assert item.status is WatchStatus.IMPROVED

    def test_an_improved_item_resolves_once_the_signal_stops(self) -> None:
        improved = review(
            opened(14.0),
            "2025-Q4",
            [dso_signal()],
            {"days_sales_outstanding": series(40.0, 54.0, 58.0)},
            THRESHOLDS,
        )
        assert improved.status is WatchStatus.IMPROVED

        resolved = review(
            improved,
            "2026-Q1",
            [],
            {"days_sales_outstanding": series(40.0, 54.0, 58.0, 41.0)},
            THRESHOLDS,
        )

        assert resolved.status is WatchStatus.RESOLVED
        assert resolved.resolved_in_period == "2026-Q1"

    def test_the_signal_no_longer_firing_is_what_resolves_it(self) -> None:
        """Resolution borrows the threshold's own account of a normal range
        rather than inventing a second one."""
        item = review(
            opened(14.0),
            "2025-Q4",
            [],
            {"days_sales_outstanding": series(40.0, 54.0, 41.0)},
            THRESHOLDS,
        )

        assert item.status is WatchStatus.RESOLVED

    def test_a_move_below_the_floor_changes_nothing(self) -> None:
        """From +14.0 days to +14.4. The floor exists so rounding is not a
        story."""
        item = review(
            opened(14.0),
            "2025-Q4",
            [dso_signal()],
            {"days_sales_outstanding": series(40.0, 54.0, 68.4)},
            THRESHOLDS,
        )

        assert item.status is WatchStatus.OPEN


class TestMissingDataIsNotGoodNews:
    def test_a_null_metric_is_not_measurable(self) -> None:
        item = review(
            opened(14.0),
            "2025-Q4",
            [dso_signal()],
            {"days_sales_outstanding": series(40.0, 54.0, None)},
            THRESHOLDS,
        )

        assert item.status is WatchStatus.NOT_MEASURABLE

    def test_not_measurable_does_not_close_the_item(self) -> None:
        item = review(
            opened(14.0),
            "2025-Q4",
            [dso_signal()],
            {"days_sales_outstanding": series(40.0, 54.0, None)},
            THRESHOLDS,
        )

        assert item.status.is_closed is False
        assert item.is_open_business
        assert item.resolved_in_period is None

    def test_a_metric_that_vanished_entirely_is_not_measurable(self) -> None:
        item = review(opened(14.0), "2025-Q4", [], {}, THRESHOLDS)

        assert item.status is WatchStatus.NOT_MEASURABLE

    def test_the_question_is_picked_back_up_when_the_data_returns(self) -> None:
        paused = review(
            opened(14.0),
            "2025-Q4",
            [dso_signal()],
            {"days_sales_outstanding": series(40.0, 54.0, None)},
            THRESHOLDS,
        )

        resumed = review(
            paused,
            "2026-Q1",
            [dso_signal()],
            {"days_sales_outstanding": series(40.0, 54.0, None, 62.0, 90.0)},
            THRESHOLDS,
        )

        assert resumed.status is WatchStatus.WORSENED
        assert [status for _, status in resumed.history] == [
            WatchStatus.NOT_MEASURABLE,
            WatchStatus.WORSENED,
        ]


class TestWhatItCarries:
    def test_a_resolved_item_is_never_reopened(self) -> None:
        resolved = review(
            opened(14.0),
            "2025-Q4",
            [],
            {"days_sales_outstanding": series(40.0, 54.0, 41.0)},
            THRESHOLDS,
        )

        again = review(
            resolved,
            "2026-Q1",
            [dso_signal()],
            {"days_sales_outstanding": series(40.0, 54.0, 41.0, 90.0)},
            THRESHOLDS,
        )

        assert again is resolved

    def test_the_opening_reading_survives_every_review(self) -> None:
        item = opened(14.0)
        for period, values in (
            ("2025-Q4", (40.0, 54.0, 76.0)),
            ("2026-Q1", (40.0, 54.0, 76.0, 80.0)),
        ):
            item = review(
                item,
                period,
                [dso_signal()],
                {"days_sales_outstanding": series(*values)},
                THRESHOLDS,
            )

        assert item.opened_from.year_on_year_change == 14.0
        assert item.opened_in_period == "2025-Q3"
        assert item.current is not None
        assert item.current.period_code == "2026-Q1"

    def test_every_review_is_recorded_in_order(self) -> None:
        item = review(
            opened(14.0),
            "2025-Q4",
            [dso_signal()],
            {"days_sales_outstanding": series(40.0, 54.0, 76.0)},
            THRESHOLDS,
        )
        item = review(
            item,
            "2026-Q1",
            [dso_signal()],
            {"days_sales_outstanding": series(40.0, 54.0, 76.0, 58.0)},
            THRESHOLDS,
        )

        assert item.history == (
            ("2025-Q4", WatchStatus.WORSENED),
            ("2026-Q1", WatchStatus.IMPROVED),
        )

    def test_a_status_carries_a_key_and_never_a_sentence(self) -> None:
        item = review(
            opened(14.0),
            "2025-Q4",
            [dso_signal()],
            {"days_sales_outstanding": series(40.0, 54.0, 76.0)},
            THRESHOLDS,
        )

        assert item.status_reason.startswith("watch.")
        assert " " not in item.status_reason
