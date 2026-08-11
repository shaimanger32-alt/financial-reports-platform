"""Accounting identities.

Spec section 21.2: when the data allows it, check that the statements add up.

    Assets = Liabilities + Equity
    Gross profit = Revenue - Cost of sales

A failure here does not mean the issuer is wrong. Far more often it means we
mapped a concept to the wrong metric, or mixed a consolidated figure with a
separate one. That is precisely why the check is worth having: it catches our
mistakes before they reach a user as a confident-looking number.

Tolerance is relative, because a rounding difference on a figure in the billions
is not the same size as one on a figure in the thousands.
"""

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from enum import StrEnum
from typing import Final

Figures = Mapping[str, float | None]

# Filings are tagged to the thousand, so a discrepancy below this is rounding.
RELATIVE_TOLERANCE: Final[float] = 0.005
ABSOLUTE_TOLERANCE: Final[float] = 1_000.0


class IdentityOutcome(StrEnum):
    """The result of checking one identity."""

    HOLDS = "holds"
    BROKEN = "broken"
    NOT_CHECKABLE = "not_checkable"
    """An input is missing, so nothing can be concluded. Not a failure."""


@dataclass(frozen=True, slots=True)
class IdentityCheck:
    """One identity, checked against one period's figures."""

    name: str
    outcome: IdentityOutcome
    expected: float | None = None
    actual: float | None = None
    missing: tuple[str, ...] = ()

    @property
    def difference(self) -> float | None:
        if self.expected is None or self.actual is None:
            return None
        return self.actual - self.expected

    @property
    def relative_difference(self) -> float | None:
        """Size of the gap against the larger side, so it can be compared."""
        if self.expected is None or self.actual is None:
            return None
        scale = max(abs(self.expected), abs(self.actual))
        if scale == 0.0:
            return 0.0
        return abs(self.actual - self.expected) / scale

    @property
    def holds(self) -> bool:
        return self.outcome is IdentityOutcome.HOLDS


def within_tolerance(expected: float, actual: float) -> bool:
    """Whether two figures agree once rounding is allowed for."""
    scale = max(abs(expected), abs(actual))
    return abs(actual - expected) <= max(ABSOLUTE_TOLERANCE, RELATIVE_TOLERANCE * scale)


def _evaluate(
    name: str,
    figures: Figures,
    required: tuple[str, ...],
    expected_of: Callable[[dict[str, float]], float],
    actual_key: str,
) -> IdentityCheck:
    """Run one identity, or explain why it could not be run."""
    missing = tuple(key for key in required if figures.get(key) is None)
    if missing:
        return IdentityCheck(name=name, outcome=IdentityOutcome.NOT_CHECKABLE, missing=missing)

    present = {key: float(value) for key in required if (value := figures[key]) is not None}
    expected = expected_of(present)
    actual = present[actual_key]

    outcome = (
        IdentityOutcome.HOLDS if within_tolerance(expected, actual) else IdentityOutcome.BROKEN
    )
    return IdentityCheck(name=name, outcome=outcome, expected=expected, actual=actual)


def check_balance_sheet(figures: Figures) -> IdentityCheck:
    """Assets = current liabilities + non-current liabilities + equity.

    Total liabilities is tagged by only a third of issuers, so the two halves are
    summed instead. Equity is the total including minority interests, which is
    the figure this identity needs.
    """
    return _evaluate(
        name="assets_equal_liabilities_plus_equity",
        figures=figures,
        required=(
            "total_assets",
            "current_liabilities",
            "non_current_liabilities",
            "total_equity",
        ),
        expected_of=lambda v: (
            v["current_liabilities"] + v["non_current_liabilities"] + v["total_equity"]
        ),
        actual_key="total_assets",
    )


def check_gross_profit(figures: Figures) -> IdentityCheck:
    """Gross profit = revenue - cost of sales.

    Cost of sales is tagged as a positive magnitude in this taxonomy, so its
    absolute value is subtracted. Taking the sign on trust would turn a healthy
    margin into a nonsensical one for any issuer that tags it negative.
    """
    return _evaluate(
        name="gross_profit_equals_revenue_less_cost_of_sales",
        figures=figures,
        required=("revenue", "cost_of_sales", "gross_profit"),
        expected_of=lambda v: v["revenue"] - abs(v["cost_of_sales"]),
        actual_key="gross_profit",
    )


def check_cash_bridge(figures: Figures) -> IdentityCheck:
    """Operating plus investing plus financing equals the change in cash.

    Every issuer tags all three cash flow sections, so unlike the other two this
    identity is checkable for the whole market. It catches a sign convention read
    the wrong way round, which is otherwise invisible: a financing outflow stored
    as a positive number still looks like a plausible figure on its own.
    """
    return _evaluate(
        name="cash_flows_sum_to_the_change_in_cash",
        figures=figures,
        required=(
            "operating_cash_flow",
            "investing_cash_flow",
            "financing_cash_flow",
            "net_change_in_cash",
        ),
        expected_of=lambda v: (
            v["operating_cash_flow"] + v["investing_cash_flow"] + v["financing_cash_flow"]
        ),
        actual_key="net_change_in_cash",
    )


def check_balance_sheet_total(figures: Figures) -> IdentityCheck:
    """Assets equals the reported total of equity and liabilities.

    Both sides are tagged by every issuer, so this is the one balance sheet check
    that always runs. `check_balance_sheet` rebuilds the other side from its
    parts and is the stronger test where those parts exist.
    """
    return _evaluate(
        name="assets_equal_reported_equity_and_liabilities",
        figures=figures,
        required=("total_assets", "equity_and_liabilities"),
        expected_of=lambda v: v["equity_and_liabilities"],
        actual_key="total_assets",
    )


def check_all(figures: Figures) -> tuple[IdentityCheck, ...]:
    """Run every identity that applies to one period's figures."""
    return (
        check_balance_sheet_total(figures),
        check_balance_sheet(figures),
        check_cash_bridge(figures),
        check_gross_profit(figures),
    )
