"""Classification of raw dates into fiscal periods.

The shapes tested here are the ones observed in real MAGNA payloads. The
rejection cases matter at least as much: a period we misclassify becomes a
number that is wrong without looking wrong.
"""

from datetime import date

import pytest

from financial_core.periods import (
    DurationKind,
    PeriodKind,
    classify,
    classify_duration,
    classify_instant,
    quarter_containing,
    quarter_of_end_date,
)


@pytest.mark.parametrize(
    ("start", "end", "quarter", "duration_kind"),
    [
        (date(2023, 1, 1), date(2023, 3, 31), 1, DurationKind.QUARTER),
        (date(2023, 1, 1), date(2023, 6, 30), 2, DurationKind.YTD),
        (date(2023, 1, 1), date(2023, 9, 30), 3, DurationKind.YTD),
        (date(2023, 1, 1), date(2023, 12, 31), 4, DurationKind.ANNUAL),
        (date(2023, 4, 1), date(2023, 6, 30), 2, DurationKind.QUARTER),
        (date(2023, 7, 1), date(2023, 9, 30), 3, DurationKind.QUARTER),
        (date(2023, 10, 1), date(2023, 12, 31), 4, DurationKind.QUARTER),
    ],
)
def test_every_shape_magna_actually_returns(
    start: date,
    end: date,
    quarter: int,
    duration_kind: DurationKind,
) -> None:
    period = classify_duration(start, end)

    assert period is not None
    assert period.fiscal_year == 2023
    assert period.fiscal_quarter == quarter
    assert period.duration_kind is duration_kind
    assert period.period_kind is PeriodKind.DURATION


def test_q1_is_a_quarter_and_also_year_to_date() -> None:
    """Q1 is both. Classified as a quarter, honest about the rest."""
    period = classify_duration(date(2023, 1, 1), date(2023, 3, 31))

    assert period is not None
    assert period.duration_kind is DurationKind.QUARTER
    assert period.is_year_to_date is True


def test_discrete_quarter_is_not_year_to_date() -> None:
    period = classify_duration(date(2023, 4, 1), date(2023, 6, 30))

    assert period is not None
    assert period.is_year_to_date is False


@pytest.mark.parametrize(
    ("start", "end", "expected_days"),
    [
        (date(2023, 1, 1), date(2023, 3, 31), 90),
        (date(2023, 4, 1), date(2023, 6, 30), 91),
        (date(2023, 7, 1), date(2023, 9, 30), 92),
        (date(2024, 1, 1), date(2024, 3, 31), 91),
        (date(2024, 1, 1), date(2024, 12, 31), 366),
    ],
)
def test_days_uses_the_real_calendar(start: date, end: date, expected_days: int) -> None:
    """Section 13.4 prefers actual days in period over a hard-coded 91."""
    period = classify_duration(start, end)

    assert period is not None
    assert period.days == expected_days


@pytest.mark.parametrize(
    ("start", "end"),
    [
        (date(2023, 2, 15), date(2023, 6, 30)),  # stub period after a listing
        (date(2023, 4, 1), date(2023, 7, 31)),  # non-calendar fiscal quarter
        (date(2022, 7, 1), date(2023, 6, 30)),  # trailing twelve months
        (date(2023, 1, 1), date(2023, 5, 31)),  # five months
        (date(2023, 6, 30), date(2023, 1, 1)),  # reversed
        (date(2023, 4, 1), date(2023, 6, 29)),  # a day short
    ],
)
def test_unrecognised_shapes_are_rejected(start: date, end: date) -> None:
    """Unclassified is a usable answer. A wrong quarter is not."""
    assert classify_duration(start, end) is None


def test_instant_at_a_quarter_end_is_accepted() -> None:
    period = classify_instant(date(2023, 6, 30))

    assert period is not None
    assert period.period_kind is PeriodKind.INSTANT
    assert period.duration_kind is None
    assert period.fiscal_year == 2023
    assert period.fiscal_quarter == 2
    assert period.days is None


def test_instant_mid_quarter_is_rejected() -> None:
    """A balance struck mid-quarter is not comparable with one at a quarter end."""
    assert classify_instant(date(2023, 5, 17)) is None


def test_classify_dispatches_on_the_presence_of_a_start() -> None:
    assert classify(None, date(2023, 12, 31)) == classify_instant(date(2023, 12, 31))
    assert classify(date(2023, 1, 1), date(2023, 12, 31)) == classify_duration(
        date(2023, 1, 1), date(2023, 12, 31)
    )


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        (date(2023, 3, 31), 1),
        (date(2023, 6, 30), 2),
        (date(2023, 9, 30), 3),
        (date(2023, 12, 31), 4),
    ],
)
def test_quarter_of_end_date(value: date, expected: int) -> None:
    assert quarter_of_end_date(value) == expected


def test_quarter_of_end_date_is_none_off_boundary() -> None:
    assert quarter_of_end_date(date(2023, 6, 29)) is None


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        (date(2023, 1, 1), 1),
        (date(2023, 5, 17), 2),
        (date(2023, 8, 2), 3),
        (date(2023, 11, 30), 4),
    ],
)
def test_quarter_containing(value: date, expected: int) -> None:
    assert quarter_containing(value) == expected


def test_period_codes_are_distinct_and_readable() -> None:
    codes = {
        classify_duration(date(2023, 1, 1), date(2023, 3, 31)),
        classify_duration(date(2023, 1, 1), date(2023, 6, 30)),
        classify_duration(date(2023, 4, 1), date(2023, 6, 30)),
        classify_duration(date(2023, 1, 1), date(2023, 12, 31)),
    }
    rendered = {p.code for p in codes if p is not None}

    assert rendered == {"2023-Q1", "2023-YTD-Q2", "2023-Q2", "2023-FY"}


def test_previous_year_preserves_the_period_shape() -> None:
    ytd = classify_duration(date(2024, 1, 1), date(2024, 9, 30))
    assert ytd is not None

    prior = ytd.previous_year()

    assert prior.code == "2023-YTD-Q3"
    assert prior.start == date(2023, 1, 1)
    assert prior.end == date(2023, 9, 30)
    assert prior.duration_kind is DurationKind.YTD


def test_previous_year_of_a_discrete_quarter_stays_discrete() -> None:
    quarter = classify_duration(date(2024, 7, 1), date(2024, 9, 30))
    assert quarter is not None

    prior = quarter.previous_year()

    assert prior.code == "2023-Q3"
    assert prior.start == date(2023, 7, 1)
    assert prior.is_year_to_date is False


def test_previous_year_of_an_instant_stays_an_instant() -> None:
    instant = classify_instant(date(2024, 6, 30))
    assert instant is not None

    prior = instant.previous_year()

    assert prior.period_kind is PeriodKind.INSTANT
    assert prior.end == date(2023, 6, 30)
