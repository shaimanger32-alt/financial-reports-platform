"""Report Pulse dimensions, as data (spec section 6.1).

Five dimensions, not six. Section 6.1 lists six and section 26.2 shows five;
Shay settled it on 2026-08-12 in favour of five, dropping Shareholder Quality.
The reason is coverage: dilution resolves for some issuers and not others, and a
row that reads "no data" at half the market teaches a reader to skip the whole
band.

**No new threshold was invented to build this, and that is the point.** A
dimension's state is read off the signals that already fired in it, and those
signals already carry a severity decided in question D of the methodology. The
mapping is:

    a `warning` or `critical` signal   ->  weak
    a `watch` signal                   ->  watch
    only positive signals              ->  strong
    nothing fired, metrics resolve     ->  stable
    no metric in the dimension resolves->  no data

So Report Pulse says nothing the signal engine had not already established. It
regroups it into the five questions a reader actually arrives with, which is
what section 6.1 asks for.
"""

from dataclasses import dataclass
from enum import StrEnum
from typing import Final

PULSE_VERSION: Final[str] = "v1"


class PulseState(StrEnum):
    """How a dimension reads this period.

    Deliberately not a score. Section 6.1: "לא להציג בהכרח ציון 0-100" — a
    number invites a league table, and this product does not grade companies.
    """

    STRONG = "strong"
    STABLE = "stable"
    WATCH = "watch"
    WEAK = "weak"
    NO_DATA = "no_data"
    """The company reports nothing this dimension is built from. Not a verdict
    of any kind, and never shown as one (spec section 4.4)."""

    @property
    def is_concerning(self) -> bool:
        return self in {PulseState.WATCH, PulseState.WEAK}


@dataclass(frozen=True, slots=True)
class PulseDimension:
    """One of the five questions a reader arrives with."""

    code: str
    message_key: str
    signal_codes: tuple[str, ...]
    """Signals that speak to this dimension."""
    metric_codes: tuple[str, ...]
    """Metrics whose availability decides whether the dimension can be read at
    all. Without one of these the dimension is `no_data`, not `stable` — silence
    because nothing was measured is not the same as silence because nothing
    moved."""
    version: str = PULSE_VERSION
    note: str | None = None


DIMENSIONS: Final[tuple[PulseDimension, ...]] = (
    PulseDimension(
        code="growth",
        message_key="pulse.growth",
        signal_codes=("SIG_REVENUE_ACCELERATION",),
        metric_codes=("revenue_growth_yoy", "net_income_growth_yoy"),
        note="Revenue is tagged by 86% of issuers and by no bank at all in the "
        "ordinary sense, so profit growth carries the dimension where it is absent.",
    ),
    PulseDimension(
        code="profitability",
        message_key="pulse.profitability",
        signal_codes=(
            "SIG_MARGIN_EXPANSION",
            "SIG_MARGIN_COMPRESSION",
            "SIG_PROFIT_ACCELERATION",
            "SIG_TAX_RATE_INCREASE",
        ),
        metric_codes=("operating_margin", "net_margin", "effective_tax_rate"),
    ),
    PulseDimension(
        code="earnings_quality",
        message_key="pulse.earnings_quality",
        signal_codes=(
            "SIG_EARNINGS_CASH_DIVERGENCE",
            "SIG_ACCRUALS_ELEVATED",
            "SIG_OPERATING_CASH_DETERIORATION",
        ),
        metric_codes=("cash_conversion", "accruals_proxy"),
        note="Every input is CORE in both markets, so this dimension reads for "
        "every company including banks. It is the one that never goes grey.",
    ),
    PulseDimension(
        code="working_capital",
        message_key="pulse.working_capital",
        signal_codes=(
            "SIG_DSO_DETERIORATION",
            "SIG_INVENTORY_BUILD",
            "SIG_RECEIVABLES_GROWTH_GAP",
        ),
        metric_codes=(
            "days_sales_outstanding",
            "cash_conversion_cycle",
            "receivables_growth_gap",
        ),
        note="Grey at a bank and at a services company with no inventory, both "
        "of which is correct rather than missing.",
    ),
    PulseDimension(
        code="financial_strength",
        message_key="pulse.financial_strength",
        signal_codes=(
            "SIG_LIQUIDITY_DETERIORATION",
            "SIG_LEVERAGE_INCREASE",
            "SIG_EQUITY_EROSION",
            "SIG_DEBT_BUILD",
        ),
        metric_codes=("equity_ratio", "liabilities_to_equity", "current_ratio"),
    ),
)

DIMENSIONS_BY_CODE: Final[dict[str, PulseDimension]] = {
    dimension.code: dimension for dimension in DIMENSIONS
}
