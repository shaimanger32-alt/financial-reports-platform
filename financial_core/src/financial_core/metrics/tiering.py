"""Which metrics are dependable, per market.

Decision 0010 introduced two tiers from a measurement across the Israeli market:
a `CORE` metric rests only on concepts every issuer tags, so it works for every
company including a bank. That promise is the tier's whole value, and it is a
claim about a market rather than about a formula.

Decision 0011 is what forces this module to exist. Measured across forty-seven
American issuers, the same promise does not hold for the same metrics. IFRS
requires a current and non-current split on the balance sheet; US GAAP does not,
and a bank presents an unclassified balance sheet ordered by liquidity instead.
JPMorgan, Morgan Stanley, Goldman Sachs and Bank of America tag neither
`AssetsCurrent` nor `LiabilitiesCurrent`, so working capital, the current ratio
and the quick ratio resolve for 89% of that market and not for all of it.

So the tier stops being a constant on the metric and becomes a lookup against
the market being read. The same metric is `CORE` in Israel and `EXTENDED` in the
United States, and the sentence "a CORE metric works for every company" stays
true because it is now scoped to a market.

A tiering carries a version, like every other analytical rule (spec section 0,
rule 8). Nothing here is a threshold and nothing was chosen: every override
below records a coverage measurement, and the measurement is named next to it.
"""

from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Final

from financial_core.metrics.catalogue import MetricTier

TIERING_VERSION: Final[str] = "v1"


@dataclass(frozen=True, slots=True)
class MarketTiering:
    """How dependable each metric is in one market."""

    code: str
    """Stable identifier, e.g. `il_ifrs` or `us_gaap`."""
    overrides: Mapping[str, MetricTier] = field(default_factory=dict)
    """Metric code to the tier it holds *here*. A metric absent from this map
    keeps the tier the catalogue gives it."""
    version: str = TIERING_VERSION
    note: str | None = None

    def tier_of(self, metric_code: str, catalogue_tier: MetricTier) -> MetricTier:
        """The tier this metric holds in this market."""
        return self.overrides.get(metric_code, catalogue_tier)

    def is_core(self, metric_code: str, catalogue_tier: MetricTier) -> bool:
        return self.tier_of(metric_code, catalogue_tier) is MetricTier.CORE


# The catalogue's own tiers were measured against the Israeli market, so this
# tiering overrides nothing. It exists so that no caller has to special-case
# "the market with no overrides".
ISRAEL_IFRS: Final[MarketTiering] = MarketTiering(
    code="il_ifrs",
    note="Decision 0010, measured across every entity that filed iXBRL in 2024.",
)

UNITED_STATES_GAAP: Final[MarketTiering] = MarketTiering(
    code="us_gaap",
    overrides={
        # 89%. A bank orders its balance sheet by liquidity and tags neither
        # AssetsCurrent nor LiabilitiesCurrent, so anything built on the
        # current/non-current split cannot be promised for the whole market.
        "current_assets": MetricTier.EXTENDED,
        "current_liabilities": MetricTier.EXTENDED,
        "non_current_assets": MetricTier.EXTENDED,
        "non_current_liabilities": MetricTier.EXTENDED,
        "working_capital": MetricTier.EXTENDED,
        "current_ratio": MetricTier.EXTENDED,
        "quick_ratio": MetricTier.EXTENDED,
        # 89% and 55%. `InterestAndDividendIncomeOperating` would lift finance
        # income well above 55%, and is excluded because for a bank it is
        # operating revenue rather than a financing item.
        "finance_costs": MetricTier.EXTENDED,
        "finance_income": MetricTier.EXTENDED,
        "net_finance_cost": MetricTier.EXTENDED,
        # 96%, against 100% under IFRS.
        "comprehensive_income": MetricTier.EXTENDED,
        # Better here than in Israel, where share counts were tagged by three
        # and four entities. Not promoted to CORE: 96% and 98% is not everyone,
        # and the tier means everyone.
        "weighted_average_shares_basic": MetricTier.EXTENDED,
        "weighted_average_shares_diluted": MetricTier.EXTENDED,
    },
    note="Decision 0011, measured across forty-seven issuers in 2026.",
)

TIERINGS_BY_CODE: Final[dict[str, MarketTiering]] = {
    tiering.code: tiering for tiering in (ISRAEL_IFRS, UNITED_STATES_GAAP)
}

DEFAULT_TIERING: Final[MarketTiering] = ISRAEL_IFRS
