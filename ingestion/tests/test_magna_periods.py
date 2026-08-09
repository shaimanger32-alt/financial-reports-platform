"""Period parsing.

The instant/duration distinction is the single most consequential thing this
parser gets right or wrong, so the failure modes are tested as carefully as the
happy path.
"""

from datetime import date

import pytest

from ingestion.providers.magna_xbrl import PeriodParseError, parse_period


def test_instant_is_recognised() -> None:
    period = parse_period("31/12/2022")

    assert period.kind == "instant"
    assert period.end == date(2022, 12, 31)
    assert period.start is None
    assert period.days is None


def test_duration_is_recognised() -> None:
    period = parse_period("01/01/2023 - 30/06/2023")

    assert period.kind == "duration"
    assert period.start == date(2023, 1, 1)
    assert period.end == date(2023, 6, 30)


@pytest.mark.parametrize(
    ("raw", "expected_days"),
    [
        ("01/01/2023 - 31/03/2023", 90),
        ("01/04/2023 - 30/06/2023", 91),
        ("01/07/2023 - 30/09/2023", 92),
        ("01/01/2023 - 31/12/2023", 365),
        ("01/01/2024 - 31/12/2024", 366),
    ],
)
def test_duration_length_uses_actual_calendar_days(raw: str, expected_days: int) -> None:
    """Spec section 13.4 prefers real days in period over a hard-coded 91."""
    assert parse_period(raw).days == expected_days


def test_dates_are_day_first_not_month_first() -> None:
    """MAGNA uses dd/mm/yyyy. Reading it as mm/dd would silently shift periods."""
    period = parse_period("03/07/2023")

    assert period.end == date(2023, 7, 3)


@pytest.mark.parametrize(
    "raw",
    [
        "",
        "   ",
        "2023-06-30",
        "31/12/22",
        "30/02/2023",
        "01/01/2023 -- 30/06/2023",
        "01/01/2023 - ",
    ],
)
def test_unreadable_periods_raise(raw: str) -> None:
    """A period we cannot read must fail loudly, never be guessed."""
    with pytest.raises(PeriodParseError):
        parse_period(raw)


def test_reversed_range_is_rejected() -> None:
    with pytest.raises(PeriodParseError):
        parse_period("30/06/2023 - 01/01/2023")
