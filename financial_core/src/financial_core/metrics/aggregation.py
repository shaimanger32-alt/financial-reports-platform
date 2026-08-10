"""Trailing twelve months, and balance sheet averages.

Two rules from the spec drive everything here:

* Section 14.6 -- a trailing twelve month figure is four discrete quarters, never
  a year-to-date figure stretched to look like one.
* Section 13.4 -- when a ratio divides a balance by a flow, the balance is
  averaged over the period, because a snapshot at one date does not describe the
  quarter that produced the flow.

Both return `None` rather than an approximation when an input is missing.
"""

from dataclasses import dataclass

from financial_core.metrics.values import FactSet
from financial_core.periods import (
    DurationKind,
    FiscalPeriod,
    PeriodKind,
    discrete_period,
    quarter_end,
)


@dataclass(frozen=True, slots=True)
class TrailingTwelveMonths:
    """A twelve month total and the quarters that make it up."""

    value: float
    quarters: tuple[FiscalPeriod, ...]


def trailing_quarters(period: FiscalPeriod, count: int = 4) -> list[FiscalPeriod]:
    """The `count` discrete quarters ending with `period`, oldest first."""
    quarters: list[FiscalPeriod] = []
    year, quarter = period.fiscal_year, period.fiscal_quarter
    for _ in range(count):
        quarters.append(discrete_period(year, quarter))
        quarter -= 1
        if quarter == 0:
            quarter = 4
            year -= 1
    return list(reversed(quarters))


def trailing_twelve_months(
    facts: FactSet, metric_code: str, period: FiscalPeriod
) -> TrailingTwelveMonths | None:
    """Sum four discrete quarters ending at `period`.

    Returns None if any of the four is missing. Three quarters plus a gap is not
    a year, and presenting it as one would understate every ratio built on it.
    """
    quarters = trailing_quarters(period)
    total = 0.0
    for quarter in quarters:
        value = facts.value(metric_code, quarter)
        if value is None:
            return None
        total += value
    return TrailingTwelveMonths(value=total, quarters=tuple(quarters))


def balance_at(facts: FactSet, metric_code: str, period: FiscalPeriod) -> float | None:
    """A balance sheet figure at the close of `period`."""
    instant = FiscalPeriod(
        fiscal_year=period.fiscal_year,
        fiscal_quarter=period.fiscal_quarter,
        period_kind=PeriodKind.INSTANT,
        duration_kind=None,
        end=quarter_end(period.fiscal_year, period.fiscal_quarter),
    )
    return facts.value(metric_code, instant)


def average_balance(
    facts: FactSet, metric_code: str, period: FiscalPeriod
) -> tuple[float | None, bool]:
    """Average of the opening and closing balance for a period.

    Returns the average and whether both ends were available. With only the
    closing balance the closing figure is returned and the flag is False, so the
    caller can say the ratio used a point-in-time balance rather than an average
    (spec section 13.4).
    """
    closing = balance_at(facts, metric_code, period)
    if closing is None:
        return None, False

    previous_quarter = period.fiscal_quarter - 1
    previous_year = period.fiscal_year
    if previous_quarter == 0:
        previous_quarter, previous_year = 4, period.fiscal_year - 1

    opening = balance_at(facts, metric_code, discrete_period(previous_year, previous_quarter))
    if opening is None:
        return closing, False

    return (opening + closing) / 2.0, True


def days_in(period: FiscalPeriod) -> int:
    """Actual days in the period.

    Spec section 13.4 prefers the real calendar over a hard-coded 91, which is
    wrong for every quarter except the second.
    """
    days = period.days
    return days if days is not None else 91


def is_discrete_quarter(period: FiscalPeriod) -> bool:
    return (
        period.period_kind is PeriodKind.DURATION and period.duration_kind is DurationKind.QUARTER
    )
