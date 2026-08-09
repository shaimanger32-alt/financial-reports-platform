"""Turning raw dates into fiscal periods.

Classification never guesses. A date range that does not align exactly to
calendar quarter boundaries returns `None`, and the caller records the fact as
unusable rather than assigning it to a quarter it might not belong to.
"""

from datetime import date

from financial_core.periods.model import (
    QUARTER_END_MONTH_DAY,
    DurationKind,
    FiscalPeriod,
    PeriodKind,
    fiscal_year_start,
    quarter_start,
)


def quarter_of_end_date(value: date) -> int | None:
    """The fiscal quarter a date closes, or None if it is not a quarter end."""
    for quarter, (month, day) in QUARTER_END_MONTH_DAY.items():
        if (value.month, value.day) == (month, day):
            return quarter
    return None


def quarter_containing(value: date) -> int:
    """The fiscal quarter a date falls inside."""
    return (value.month - 1) // 3 + 1


def classify_instant(value: date) -> FiscalPeriod | None:
    """Classify a balance sheet date.

    Balance sheet dates are expected to close a quarter. A date that does not is
    rejected: a balance struck mid-quarter cannot be compared with one struck at
    a quarter end.
    """
    quarter = quarter_of_end_date(value)
    if quarter is None:
        return None

    return FiscalPeriod(
        fiscal_year=value.year,
        fiscal_quarter=quarter,
        period_kind=PeriodKind.INSTANT,
        duration_kind=None,
        end=value,
    )


def classify_duration(start: date, end: date) -> FiscalPeriod | None:
    """Classify a flow period.

    Recognised shapes, for a calendar fiscal year:

        Jan 1  - Mar 31   quarter 1   (also the first year-to-date period)
        Jan 1  - Jun 30   year to date, through quarter 2
        Jan 1  - Sep 30   year to date, through quarter 3
        Jan 1  - Dec 31   annual
        Apr 1  - Jun 30   quarter 2
        Jul 1  - Sep 30   quarter 3
        Oct 1  - Dec 31   quarter 4

    Anything else -- a stub period after a listing, a non-calendar fiscal year, a
    trailing twelve month window -- returns None. Trailing twelve months is
    always computed by us and never arrives from a provider.
    """
    if start > end:
        return None

    quarter = quarter_of_end_date(end)
    if quarter is None:
        return None

    fiscal_year = end.year

    if start == fiscal_year_start(fiscal_year):
        if quarter == 4:
            duration_kind = DurationKind.ANNUAL
        elif quarter == 1:
            # Identical to the first year-to-date period. Classified as a
            # quarter because that is what the analysis layer consumes;
            # `is_year_to_date` still reports the truth.
            duration_kind = DurationKind.QUARTER
        else:
            duration_kind = DurationKind.YTD
    elif start == quarter_start(fiscal_year, quarter):
        duration_kind = DurationKind.QUARTER
    else:
        return None

    return FiscalPeriod(
        fiscal_year=fiscal_year,
        fiscal_quarter=quarter,
        period_kind=PeriodKind.DURATION,
        duration_kind=duration_kind,
        start=start,
        end=end,
    )


def classify(start: date | None, end: date) -> FiscalPeriod | None:
    """Classify a period from its raw dates.

    A missing start means the figure is an instant.
    """
    return classify_instant(end) if start is None else classify_duration(start, end)
