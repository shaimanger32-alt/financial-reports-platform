"""A company's own fiscal calendar.

Israeli issuers all close on 31 December, so classification could read a quarter
straight off a date. American filers cannot be read that way. Apple's fiscal
year is 52 or 53 weeks long and ends on the last Saturday of September:

    2023-10-01 -> 2024-09-28    FY2024
    2024-09-29 -> 2025-09-27    FY2025

Its first fiscal quarter runs 2025-09-28 to 2025-12-27. Nothing about those
dates says "quarter one" to a rule built on calendar boundaries, and the old
classifier correctly refused all of them rather than guessing.

So the calendar stops being an assumption and becomes data: **the boundaries a
company itself reported**. A fiscal year is known by the window the filer tagged
as its year, and a quarter is located by how far into that window a period ends.

That needs no tolerance constant and no invented number. Quarter length is the
fiscal year's own length divided by four, so a 53-week year stretches its own
quarters and a calendar year keeps producing exactly the answers it always did.

Nothing here decides which fiscal year a company is *in*. It only recognises
periods against years the company has already declared. A date outside every
declared year stays unclassified, which is the same refusal as before.
"""

from bisect import bisect_left
from dataclasses import dataclass
from datetime import date, timedelta

from financial_core.periods.model import (
    DurationKind,
    FiscalPeriod,
    PeriodKind,
)

QUARTERS_IN_YEAR = 4


@dataclass(frozen=True, slots=True, order=True)
class FiscalYearWindow:
    """One fiscal year as the company reported it.

    `is_projected` marks the year in progress. A company's annual report is what
    declares a fiscal year's end, so the year currently being reported has no
    declared end until it finishes — and that is precisely the year a reader
    cares about. Its start is observed, from the year-to-date window every
    quarterly report opens with; its end is carried over from the length of the
    preceding year.

    That carry-over is an inference, and it is labelled as one rather than
    hidden, exactly as decision 0009 treats filing recency. For a 52/53-week
    filer it can be a week out, which moves no quarter boundary that any
    reported period lands on, but it is not a fact and does not pretend to be.
    """

    fiscal_year: int
    start: date
    end: date
    is_projected: bool = False

    def __post_init__(self) -> None:
        if self.start > self.end:
            raise ValueError("a fiscal year cannot end before it starts")

    @property
    def days(self) -> int:
        return (self.end - self.start).days + 1

    def contains(self, value: date) -> bool:
        return self.start <= value <= self.end

    def quarter_of(self, value: date) -> int | None:
        """Which quarter of this year a date closes.

        Measured as elapsed days over the year's own quarter length, rounded to
        the nearest quarter. A 52-week year gives quarters of exactly 91 days; a
        53-week year gives 91.25; a calendar year gives 91.25 as well. In every
        case the reported quarter ends land on a whole number, which is why no
        tolerance has to be chosen.
        """
        if not self.contains(value):
            return None

        elapsed = (value - self.start).days + 1
        quarter = round(elapsed / (self.days / QUARTERS_IN_YEAR))
        return min(max(quarter, 1), QUARTERS_IN_YEAR)


@dataclass(frozen=True, slots=True)
class FiscalCalendar:
    """Every fiscal year a company has declared, oldest first.

    Built from filings rather than from a rule, so a company that changes its
    year end is described correctly instead of being forced onto a pattern.
    """

    windows: tuple[FiscalYearWindow, ...]

    def __post_init__(self) -> None:
        if list(self.windows) != sorted(self.windows):
            raise ValueError("fiscal year windows must be ordered oldest first")

    @property
    def is_empty(self) -> bool:
        return not self.windows

    def window_for_year(self, fiscal_year: int) -> FiscalYearWindow | None:
        for window in self.windows:
            if window.fiscal_year == fiscal_year:
                return window
        return None

    def window_containing(self, value: date) -> FiscalYearWindow | None:
        """The declared fiscal year a date falls inside, or None.

        None is a real answer: a date before the first filing or after the last
        one belongs to a year we have not been told about, and inventing its
        boundaries would be a guess.
        """
        starts = [window.start for window in self.windows]
        index = bisect_left(starts, value)
        # `value` may open the window at `index`, or fall inside the one before.
        for candidate in (index, index - 1):
            if 0 <= candidate < len(self.windows) and self.windows[candidate].contains(value):
                return self.windows[candidate]
        return None


def quarter_bounds(window: FiscalYearWindow, quarter: int) -> tuple[date, date]:
    """The real dates of one quarter inside a company's own fiscal year.

    A derived quarter has no dates of its own — it is the difference of two
    cumulative figures — so they have to come from somewhere. Taking them from
    the calendar was wrong: Apple's fiscal 2025 fourth quarter was stored as
    1 October to 31 December when the company closed it on 27 September, three
    months earlier. The code was right and the dates a reader saw were not.

    The year is divided into four by its own length, so a 52-week year gives
    91-day quarters and a 53-week year stretches its own.
    """
    if not 1 <= quarter <= QUARTERS_IN_YEAR:
        raise ValueError(f"fiscal quarter out of range: {quarter}")

    length = window.days
    opens = round((quarter - 1) * length / QUARTERS_IN_YEAR)
    closes = round(quarter * length / QUARTERS_IN_YEAR)
    return (
        window.start + timedelta(days=opens),
        window.start + timedelta(days=closes - 1),
    )


def discrete_period_in(window: FiscalYearWindow, quarter: int) -> FiscalPeriod:
    """A standalone quarter carrying the dates the company actually closed on."""
    start, end = quarter_bounds(window, quarter)
    return FiscalPeriod(
        fiscal_year=window.fiscal_year,
        fiscal_quarter=quarter,
        period_kind=PeriodKind.DURATION,
        duration_kind=DurationKind.QUARTER,
        start=start,
        end=end,
    )


def calendar_year_window(fiscal_year: int) -> FiscalYearWindow:
    """The fiscal year of an issuer that closes on 31 December."""
    return FiscalYearWindow(
        fiscal_year=fiscal_year,
        start=date(fiscal_year, 1, 1),
        end=date(fiscal_year, 12, 31),
    )


def calendar_year_calendar(first_year: int, last_year: int) -> FiscalCalendar:
    """A calendar-year fiscal calendar, which is every Israeli issuer we hold."""
    return FiscalCalendar(
        tuple(calendar_year_window(year) for year in range(first_year, last_year + 1))
    )


def classify_instant_in(value: date, calendar: FiscalCalendar) -> FiscalPeriod | None:
    """Classify a balance sheet date against a company's own calendar.

    Unlike the calendar-year classifier, this does not require the date to be a
    quarter end. Apple's balance sheet is struck on 2025-12-27, which closes its
    first fiscal quarter and is not the end of any calendar quarter. Refusing it
    would discard the entire balance sheet.
    """
    window = calendar.window_containing(value)
    if window is None:
        return None

    quarter = window.quarter_of(value)
    if quarter is None:
        return None

    return FiscalPeriod(
        fiscal_year=window.fiscal_year,
        fiscal_quarter=quarter,
        period_kind=PeriodKind.INSTANT,
        duration_kind=None,
        end=value,
    )


def classify_duration_in(
    start: date,
    end: date,
    calendar: FiscalCalendar,
) -> FiscalPeriod | None:
    """Classify a flow period against a company's own calendar.

    The shape is read from where the period sits in the fiscal year, exactly as
    it is for a calendar-year issuer:

        opens the year, closes the year      annual
        opens the year, closes earlier       year to date
        opens mid-year                       a discrete quarter

    A window that spans more than one fiscal year, or that opens inside a year
    without closing in the same one, returns None. Trailing twelve months is
    always computed by us and never arrives from a filer.
    """
    if start > end:
        return None

    window = calendar.window_containing(end)
    if window is None or not window.contains(start):
        return None

    quarter = window.quarter_of(end)
    if quarter is None:
        return None

    if start == window.start:
        if quarter == QUARTERS_IN_YEAR:
            duration_kind = DurationKind.ANNUAL
        elif quarter == 1:
            # Q1 is a discrete quarter and the first year-to-date window at
            # once. Classified as a quarter because that is what the analysis
            # layer consumes; `is_year_to_date` still reports the truth.
            duration_kind = DurationKind.QUARTER
        else:
            duration_kind = DurationKind.YTD
    else:
        duration_kind = DurationKind.QUARTER

    return FiscalPeriod(
        fiscal_year=window.fiscal_year,
        fiscal_quarter=quarter,
        period_kind=PeriodKind.DURATION,
        duration_kind=duration_kind,
        start=start,
        end=end,
    )


def classify_in(
    start: date | None,
    end: date,
    calendar: FiscalCalendar,
) -> FiscalPeriod | None:
    """Classify a period against a company's own calendar.

    A missing start means the figure is an instant.
    """
    if calendar.is_empty:
        return None
    if start is None:
        return classify_instant_in(end, calendar)
    return classify_duration_in(start, end, calendar)
