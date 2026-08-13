"""Tiering per market.

Decision 0010 promised that a `CORE` metric works for every company in the
market. Decision 0011 found that the same metrics cannot keep that promise in
the United States, because US GAAP does not require the current/non-current
balance sheet split that IFRS does.

These tests hold the promise itself, not the list. If someone marks a metric
CORE in a market where its inputs are not universal, the tier stops meaning
anything and the honest `null` it was supposed to guarantee turns into a gap.
"""

import pytest

from financial_core.metrics import (
    CALCULATED_BY_CODE,
    DEFAULT_TIERING,
    ISRAEL_IFRS,
    METRICS_BY_CODE,
    TIERING_VERSION,
    TIERINGS_BY_CODE,
    UNITED_STATES_GAAP,
    MarketTiering,
    MetricTier,
)

# Every metric whose inputs include the current/non-current split. Measured at
# 89% of American issuers: a bank orders its balance sheet by liquidity.
NEEDS_CURRENT_SPLIT = (
    "current_assets",
    "current_liabilities",
    "working_capital",
    "current_ratio",
    "quick_ratio",
)


def _tier(tiering: MarketTiering, code: str) -> MetricTier:
    spec = CALCULATED_BY_CODE.get(code) or METRICS_BY_CODE.get(code)
    assert spec is not None, f"unknown metric {code}"
    return tiering.tier_of(code, spec.tier)


class TestTheUnitedStates:
    @pytest.mark.parametrize("code", NEEDS_CURRENT_SPLIT)
    def test_liquidity_is_not_core_here(self, code: str) -> None:
        assert _tier(UNITED_STATES_GAAP, code) is MetricTier.EXTENDED

    @pytest.mark.parametrize("code", NEEDS_CURRENT_SPLIT)
    def test_the_same_metrics_are_core_in_israel(self, code: str) -> None:
        """The whole point of the change: the metric did not get worse, the
        market is different."""
        assert _tier(ISRAEL_IFRS, code) is MetricTier.CORE

    @pytest.mark.parametrize(
        "code",
        ["net_income", "total_assets", "total_equity", "operating_cash_flow", "cash_conversion"],
    )
    def test_what_survives_on_both_sides(self, code: str) -> None:
        """Profitability, capital structure, earnings quality and cash are the
        floor in either market."""
        assert _tier(UNITED_STATES_GAAP, code) is MetricTier.CORE
        assert _tier(ISRAEL_IFRS, code) is MetricTier.CORE

    def test_finance_income_loses_core(self) -> None:
        """55%. Padding the chain would make a bank's core business read as a
        treasury position, so the coverage stands and the tier drops."""
        assert _tier(UNITED_STATES_GAAP, "finance_income") is MetricTier.EXTENDED

    def test_share_counts_improve_without_being_promoted(self) -> None:
        """96% and 98% here against three and four Israeli entities. Better is
        not everyone, and the tier means everyone."""
        for code in ("weighted_average_shares_basic", "weighted_average_shares_diluted"):
            assert _tier(UNITED_STATES_GAAP, code) is MetricTier.EXTENDED


class TestTheMechanism:
    def test_israel_overrides_nothing(self) -> None:
        """The catalogue's tiers were measured against the Israeli market, so
        this tiering exists only so callers need no special case."""
        assert ISRAEL_IFRS.overrides == {}

    def test_the_default_is_israel(self) -> None:
        assert DEFAULT_TIERING is ISRAEL_IFRS

    def test_a_metric_not_overridden_keeps_its_catalogue_tier(self) -> None:
        assert UNITED_STATES_GAAP.tier_of("net_income", MetricTier.CORE) is MetricTier.CORE
        assert UNITED_STATES_GAAP.tier_of("gross_margin", MetricTier.EXTENDED) is (
            MetricTier.EXTENDED
        )

    def test_every_override_names_a_real_metric(self) -> None:
        """A typo would silently leave a metric on the wrong tier."""
        known = set(CALCULATED_BY_CODE) | set(METRICS_BY_CODE)
        for tiering in TIERINGS_BY_CODE.values():
            unknown = set(tiering.overrides) - known
            assert not unknown, f"{tiering.code} overrides unknown metrics: {sorted(unknown)}"

    def test_no_override_promotes_a_metric_to_core(self) -> None:
        """A tiering may only be more conservative than the catalogue. Promoting
        would assert universal coverage that nothing here measured."""
        for tiering in TIERINGS_BY_CODE.values():
            for code, tier in tiering.overrides.items():
                assert tier is MetricTier.EXTENDED, f"{tiering.code} promotes {code}"

    def test_every_tiering_is_versioned_and_named(self) -> None:
        for code, tiering in TIERINGS_BY_CODE.items():
            assert tiering.code == code
            assert tiering.version == TIERING_VERSION
            assert tiering.note, f"{code} does not say what measured it"
