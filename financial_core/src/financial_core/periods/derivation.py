"""Deriving discrete quarters from cumulative reporting.

Israeli issuers report Q1, H1, nine months and a full year. The phase 1 spike
established that Q2 and Q3 *are* also reported as standalone quarters, and that
Q4 never is. So Q4 always has to be derived, and for Q2 and Q3 a derivation
exists as a cross-check against the issuer's own figure.

Per decision 0009, a derivation never replaces a reported value. Both are kept,
and a disagreement between them is surfaced rather than resolved silently.

Only flows may be differenced. Balances are snapshots: subtracting one balance
date from another does not produce a quarter, it produces a movement, and the
two must never be confused. `derive_quarter` refuses instants outright.
"""

from collections.abc import Callable
from dataclasses import dataclass
from typing import Final

from financial_core.periods.model import (
    DurationKind,
    FiscalPeriod,
    PeriodKind,
    fiscal_year_start,
    quarter_end,
    quarter_start,
)

ValueLookup = Callable[[FiscalPeriod], float | None]

# Reported figures are whole currency units, so an exact match is expected.
# The floor absorbs float representation error on values in the billions.
RELATIVE_TOLERANCE: Final[float] = 1e-9
ABSOLUTE_TOLERANCE: Final[float] = 1.0


class DerivationNotApplicableError(ValueError):
    """The requested derivation is meaningless for this kind of period."""


@dataclass(frozen=True, slots=True)
class QuarterDerivation:
    """A discrete quarter computed from cumulative periods.

    `inputs` is what makes the result auditable: every derived figure can be
    traced to the reported figures it came from (spec section 4.2).
    """

    period: FiscalPeriod
    value: float
    formula: str
    inputs: tuple[tuple[FiscalPeriod, float], ...]

    @property
    def is_identity(self) -> bool:
        """True for Q1, where the cumulative period already is the quarter."""
        return len(self.inputs) == 1


def cumulative_period(fiscal_year: int, through_quarter: int) -> FiscalPeriod:
    """The year-to-date period running to the end of `through_quarter`."""
    if through_quarter == 4:
        duration_kind = DurationKind.ANNUAL
    elif through_quarter == 1:
        duration_kind = DurationKind.QUARTER
    else:
        duration_kind = DurationKind.YTD

    return FiscalPeriod(
        fiscal_year=fiscal_year,
        fiscal_quarter=through_quarter,
        period_kind=PeriodKind.DURATION,
        duration_kind=duration_kind,
        start=fiscal_year_start(fiscal_year),
        end=quarter_end(fiscal_year, through_quarter),
    )


def discrete_period(fiscal_year: int, quarter: int) -> FiscalPeriod:
    """The standalone quarter, independent of how it was obtained."""
    return FiscalPeriod(
        fiscal_year=fiscal_year,
        fiscal_quarter=quarter,
        period_kind=PeriodKind.DURATION,
        duration_kind=DurationKind.QUARTER,
        start=quarter_start(fiscal_year, quarter),
        end=quarter_end(fiscal_year, quarter),
    )


def derive_quarter(
    fiscal_year: int,
    quarter: int,
    lookup: ValueLookup,
) -> QuarterDerivation | None:
    """Compute a standalone quarter from cumulative figures.

    Returns None when an input is missing. A missing input is unknown, never
    zero (spec section 4.4), so no partial arithmetic is attempted.
    """
    if not 1 <= quarter <= 4:
        raise ValueError(f"fiscal quarter out of range: {quarter}")

    target = discrete_period(fiscal_year, quarter)
    current = cumulative_period(fiscal_year, quarter)
    current_value = lookup(current)
    if current_value is None:
        return None

    if quarter == 1:
        return QuarterDerivation(
            period=target,
            value=current_value,
            formula="Q1 = YTD through Q1",
            inputs=((current, current_value),),
        )

    previous = cumulative_period(fiscal_year, quarter - 1)
    previous_value = lookup(previous)
    if previous_value is None:
        return None

    return QuarterDerivation(
        period=target,
        value=current_value - previous_value,
        formula=f"Q{quarter} = {current.code} - {previous.code}",
        inputs=((current, current_value), (previous, previous_value)),
    )


def derive_quarter_for_flow(
    period_kind: PeriodKind,
    fiscal_year: int,
    quarter: int,
    lookup: ValueLookup,
) -> QuarterDerivation | None:
    """Guarded entry point that refuses to difference a balance.

    Spec section 11.3: a balance is an instant. Differencing two balance dates
    yields a movement, not a quarterly flow. Enforcing that here means it cannot
    be forgotten at a call site.
    """
    if period_kind is PeriodKind.INSTANT:
        raise DerivationNotApplicableError(
            "balance sheet instants cannot be differenced into quarters; "
            "use the balance at the quarter end instead"
        )
    return derive_quarter(fiscal_year, quarter, lookup)


def rounding_tolerance(decimals: int | None) -> float:
    """How far a derived quarter may sit from the issuer's own, from rounding alone.

    Filings are tagged with an XBRL `decimals` attribute. A value of -3 means the
    figure is stated to the nearest thousand, so it carries up to half a thousand
    of rounding error.

    A derived quarter subtracts two rounded cumulative figures, so it inherits up
    to a full unit of granularity of error. The issuer's own quarter is rounded
    too, adding another half. The bound is therefore one and a half units, and
    anything inside it is rounding rather than disagreement.

    This is why the check exists at all: Matrix IT's Q2 2023 profit is 62,822,000
    as reported and 62,823,000 as derived. That gap is the tagging granularity,
    not an arithmetic error, and treating it as one would raise a false alarm on
    a perfectly sound figure.
    """
    if decimals is None or decimals >= 0:
        return ABSOLUTE_TOLERANCE
    return 1.5 * float(10 ** abs(decimals))


def values_agree(left: float, right: float, absolute_tolerance: float | None = None) -> bool:
    """Whether a reported and a derived figure are the same number.

    `absolute_tolerance` should be the reporting granularity when it is known;
    see `rounding_tolerance`. Without it the comparison is effectively exact.
    """
    floor = ABSOLUTE_TOLERANCE if absolute_tolerance is None else absolute_tolerance
    return abs(left - right) <= max(floor, RELATIVE_TOLERANCE * abs(right))


@dataclass(frozen=True, slots=True)
class Reconciliation:
    """Comparison of an issuer's own quarter against ours."""

    period: FiscalPeriod
    reported: float | None
    derived: float | None
    agrees: bool | None
    """None when one side is missing, so nothing can be concluded."""

    @property
    def difference(self) -> float | None:
        if self.reported is None or self.derived is None:
            return None
        return self.reported - self.derived


def reconcile(
    period: FiscalPeriod,
    reported: float | None,
    derived: float | None,
    decimals: int | None = None,
) -> Reconciliation:
    """Compare the reported quarter with the derived one.

    `decimals` is the XBRL rounding attribute of the source figures. Passing it
    keeps the comparison from flagging tagging granularity as disagreement.

    A real disagreement is not resolved here. It is reported, so the data-quality
    layer can flag it and the user can be shown both figures (decision 0009).
    """
    agrees = (
        None
        if reported is None or derived is None
        else values_agree(reported, derived, rounding_tolerance(decimals))
    )
    return Reconciliation(period=period, reported=reported, derived=derived, agrees=agrees)
