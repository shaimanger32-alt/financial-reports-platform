"""Basic validation (spec section 21.1).

Almost every test here is about **not** firing. Section 21.1 asks for impossible
values "when they truly are impossible", and the qualifier is the instruction:
a negative operating profit, a negative equity and a negative cash flow are all
perfectly real, and a check that flagged them would bury the one case that
matters under a hundred that do not.
"""

import pytest

from financial_core.validation import (
    BasicIssue,
    Observation,
    check_basics,
    check_contradictory_duplicates,
    check_impossible_values,
    check_unit_consistency,
)


def observed(
    metric_code: str,
    value: float,
    *,
    period: str = "2026-Q2",
    unit: str | None = "USD",
    filing: str = "0000320193-26-000001",
    concept: str = "us-gaap:Revenues",
) -> Observation:
    return Observation(
        metric_code=metric_code,
        period_code=period,
        value=value,
        unit=unit,
        filing=filing,
        raw_concept=concept,
    )


class TestImpossibleValues:
    def test_negative_assets_are_impossible(self) -> None:
        findings = check_impossible_values([observed("total_assets", -1_000.0)])

        assert [f.issue for f in findings] == [BasicIssue.IMPOSSIBLE_VALUE]

    def test_a_filing_company_has_assets(self) -> None:
        findings = check_impossible_values([observed("total_assets", 0.0)])

        assert len(findings) == 1
        assert "assets" in findings[0].detail

    @pytest.mark.parametrize(
        "metric_code",
        ["cash_and_equivalents", "inventories", "trade_receivables", "current_assets"],
    )
    def test_you_cannot_hold_less_than_nothing(self, metric_code: str) -> None:
        assert check_impossible_values([observed(metric_code, -1.0)])

    def test_share_counts_cannot_be_negative(self) -> None:
        assert check_impossible_values([observed("weighted_average_shares_diluted", -1.0)])


class TestWhatIsRealAndMustNotFire:
    """The restraint that makes the check worth having."""

    @pytest.mark.parametrize(
        "metric_code",
        [
            "operating_profit",
            "net_income",
            "profit_before_tax",
            "gross_profit",
            "operating_cash_flow",
            "investing_cash_flow",
            "financing_cash_flow",
            "working_capital",
            "net_debt",
            "total_equity",
            "revenue_growth_yoy",
            "effect_of_exchange_rate_on_cash",
        ],
    )
    def test_a_negative_value_here_is_a_fact_not_an_error(self, metric_code: str) -> None:
        """A loss, an investing outflow, negative working capital at a retailer,
        an equity deficit after buybacks, a company shrinking. All real."""
        assert check_impossible_values([observed(metric_code, -1_000_000.0)]) == []

    def test_zero_is_only_impossible_for_the_asset_base(self) -> None:
        assert check_impossible_values([observed("inventories", 0.0)]) == []
        assert check_impossible_values([observed("net_income", 0.0)]) == []


class TestUnits:
    def test_one_unit_throughout_is_silent(self) -> None:
        assert (
            check_unit_consistency(
                [observed("revenue", 1.0, period="2025-FY"), observed("revenue", 2.0)]
            )
            == []
        )

    def test_two_units_for_one_metric_are_flagged(self) -> None:
        """Either the company changed reporting currency, which section 21.3
        wants known, or a chain resolved to something measured differently."""
        findings = check_unit_consistency(
            [
                observed("revenue", 1.0, unit="USD"),
                observed("revenue", 2.0, unit="EUR", period="2025-FY"),
            ]
        )

        assert [f.issue for f in findings] == [BasicIssue.UNIT_CHANGED]
        assert "EUR" in findings[0].detail and "USD" in findings[0].detail

    def test_metrics_in_different_units_are_not_a_conflict(self) -> None:
        """Money in dollars and a share count in shares is the normal state."""
        findings = check_unit_consistency(
            [
                observed("revenue", 1.0, unit="USD"),
                observed("weighted_average_shares_basic", 2.0, unit="shares"),
            ]
        )

        assert findings == []

    def test_an_unknown_unit_is_ignored_rather_than_guessed(self) -> None:
        assert check_unit_consistency([observed("revenue", 1.0, unit=None)]) == []


class TestContradictoryDuplicates:
    def test_one_filing_disagreeing_with_itself_is_flagged(self) -> None:
        findings = check_contradictory_duplicates(
            [observed("revenue", 100.0), observed("revenue", 200.0)]
        )

        assert [f.issue for f in findings] == [BasicIssue.CONTRADICTORY_DUPLICATE]
        assert findings[0].values == (100.0, 200.0)

    def test_the_same_value_twice_is_not_a_contradiction(self) -> None:
        """A fact repeats across a filing's own statements and notes. Repetition
        is normal; disagreement is not."""
        findings = check_contradictory_duplicates(
            [observed("revenue", 100.0), observed("revenue", 100.0)]
        )

        assert findings == []

    def test_two_concepts_in_one_chain_are_not_a_contradiction(self) -> None:
        """`net_income` resolves through both `ProfitLoss` and `NetIncomeLoss`,
        and they differ by the minority interest at every company that has one.
        Judging duplicates per metric flagged Disney on nearly every filing."""
        findings = check_contradictory_duplicates(
            [
                observed("net_income", 100.0, concept="us-gaap:ProfitLoss"),
                observed("net_income", 95.0, concept="us-gaap:NetIncomeLoss"),
            ]
        )

        assert findings == []

    def test_two_filings_disagreeing_is_a_restatement_not_this(self) -> None:
        """A later filing revising an earlier one is a real event, reported
        separately. This check is only about one document contradicting itself."""
        findings = check_contradictory_duplicates(
            [
                observed("revenue", 100.0, filing="filing-a"),
                observed("revenue", 200.0, filing="filing-b"),
            ]
        )

        assert findings == []

    def test_different_periods_in_one_filing_are_not_a_contradiction(self) -> None:
        findings = check_contradictory_duplicates(
            [
                observed("revenue", 100.0, period="2025-FY"),
                observed("revenue", 200.0, period="2026-Q2"),
            ]
        )

        assert findings == []


class TestRunningThemTogether:
    def test_a_clean_company_produces_nothing(self) -> None:
        clean = [
            observed("total_assets", 4_100_000.0),
            observed("revenue", 800_000.0),
            observed("net_income", -50_000.0),
            observed("weighted_average_shares_basic", 1_000.0, unit="shares"),
        ]

        assert check_basics(clean) == []

    def test_every_finding_is_versioned_and_explained(self) -> None:
        findings = check_basics([observed("total_assets", -1.0)])

        assert findings
        for finding in findings:
            assert finding.version
            assert finding.detail
