"""The period model.

This is the most consequential piece of domain logic in the system. Spec
section 11.3 separates instants from durations because a balance is a snapshot
and revenue is a flow, and section 14.6 forbids mixing quarter, year-to-date,
annual and trailing-twelve-month figures without an explicit normalisation step.
Getting this wrong produces numbers that look reasonable and are wrong.

Fiscal years are assumed to follow the calendar year. Every Israeli issuer in
the phase 1 sample does. A period that does not align to calendar quarters is
not guessed at: it stays unclassified, and the caller treats it as unusable.
"""

from dataclasses import dataclass
from datetime import date
from enum import StrEnum
from typing import Final

QUARTER_END_MONTH_DAY: Final[dict[int, tuple[int, int]]] = {
    1: (3, 31),
    2: (6, 30),
    3: (9, 30),
    4: (12, 31),
}

QUARTER_START_MONTH_DAY: Final[dict[int, tuple[int, int]]] = {
    1: (1, 1),
    2: (4, 1),
    3: (7, 1),
    4: (10, 1),
}


class PeriodKind(StrEnum):
    """Whether a figure is a snapshot or a flow."""

    INSTANT = "instant"
    DURATION = "duration"


class DurationKind(StrEnum):
    """How a flow period relates to the fiscal year."""

    QUARTER = "quarter"
    """A single three-month window standing alone."""

    YTD = "ytd"
    """Cumulative from the start of the fiscal year."""

    ANNUAL = "annual"
    """A complete fiscal year."""

    TTM = "ttm"
    """Trailing twelve months. Always computed by us, never reported."""


def quarter_end(fiscal_year: int, quarter: int) -> date:
    """Last day of a fiscal quarter."""
    month, day = QUARTER_END_MONTH_DAY[quarter]
    return date(fiscal_year, month, day)


def quarter_start(fiscal_year: int, quarter: int) -> date:
    """First day of a fiscal quarter."""
    month, day = QUARTER_START_MONTH_DAY[quarter]
    return date(fiscal_year, month, day)


def fiscal_year_start(fiscal_year: int) -> date:
    """First day of a fiscal year."""
    return date(fiscal_year, 1, 1)


@dataclass(frozen=True, slots=True, order=True)
class FiscalPeriod:
    """A period the system is willing to reason about.

    Instances are only ever built by the classification functions, which refuse
    to produce one for a shape they do not recognise.
    """

    fiscal_year: int
    fiscal_quarter: int
    period_kind: PeriodKind
    duration_kind: DurationKind | None
    end: date
    start: date | None = None

    def __post_init__(self) -> None:
        if not 1 <= self.fiscal_quarter <= 4:
            raise ValueError(f"fiscal quarter out of range: {self.fiscal_quarter}")
        if self.period_kind is PeriodKind.INSTANT and self.duration_kind is not None:
            raise ValueError("an instant has no duration kind")
        if self.period_kind is PeriodKind.DURATION:
            if self.duration_kind is None:
                raise ValueError("a duration needs a duration kind")
            if self.start is None:
                raise ValueError("a duration needs a start date")
            if self.start > self.end:
                raise ValueError("a duration cannot end before it starts")

    @property
    def days(self) -> int | None:
        """Actual days in the period.

        Spec section 13.4 prefers real days over a hard-coded 91 when annualising
        a working-capital ratio.
        """
        if self.start is None:
            return None
        return (self.end - self.start).days + 1

    @property
    def is_year_to_date(self) -> bool:
        """True when the period runs from the start of the fiscal year.

        Q1 is both a discrete quarter and the first year-to-date period. It is
        classified as a quarter, and this property still reports the truth.
        """
        return self.start == fiscal_year_start(self.fiscal_year)

    @property
    def code(self) -> str:
        """Stable, sortable identifier used in APIs and URLs."""
        match self.period_kind, self.duration_kind:
            case PeriodKind.INSTANT, _:
                return f"{self.fiscal_year}-Q{self.fiscal_quarter}-AT-{self.end.isoformat()}"
            case _, DurationKind.ANNUAL:
                return f"{self.fiscal_year}-FY"
            case _, DurationKind.YTD:
                return f"{self.fiscal_year}-YTD-Q{self.fiscal_quarter}"
            case _, DurationKind.TTM:
                return f"{self.fiscal_year}-TTM-Q{self.fiscal_quarter}"
            case _:
                return f"{self.fiscal_year}-Q{self.fiscal_quarter}"

    def previous_year(self) -> "FiscalPeriod":
        """The same period one year earlier, for year-on-year comparison.

        Spec section 14.1 makes year-on-year the default comparison for income
        statement and cash flow figures.
        """
        year = self.fiscal_year - 1
        if self.period_kind is PeriodKind.INSTANT:
            return FiscalPeriod(
                fiscal_year=year,
                fiscal_quarter=self.fiscal_quarter,
                period_kind=PeriodKind.INSTANT,
                duration_kind=None,
                end=quarter_end(year, self.fiscal_quarter),
            )

        assert self.duration_kind is not None  # guaranteed by __post_init__
        start = (
            fiscal_year_start(year)
            if self.is_year_to_date
            else quarter_start(year, self.fiscal_quarter)
        )
        return FiscalPeriod(
            fiscal_year=year,
            fiscal_quarter=self.fiscal_quarter,
            period_kind=PeriodKind.DURATION,
            duration_kind=self.duration_kind,
            start=start,
            end=quarter_end(year, self.fiscal_quarter),
        )
