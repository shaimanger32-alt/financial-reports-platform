"""The accounting identities (spec section 21.2).

The cases that matter are the three ways a check can be wrong:

* failing a company for reporting something we never mapped,
* passing a company because an input was missing and nothing ran,
* failing a company over rounding.

All three turn the engine into noise, and noise in a quality check is worse than
no check at all — it teaches the reader to ignore the warning that eventually
matters. The exchange-rate term below is the first of those three, caught in the
act: without it the cash bridge failed for 43 of the 54 companies in the store,
every one of them reporting properly.
"""

import pytest

from financial_core.validation import (
    IdentityOutcome,
    check_all,
    check_balance_sheet,
    check_balance_sheet_total,
    check_cash_bridge,
    check_gross_profit,
    within_tolerance,
)

# Hilan, 2025-Q4, as filed.
HILAN = {
    "total_assets": 2_972_815_000.0,
    "equity_and_liabilities": 2_972_815_000.0,
    "current_liabilities": 1_376_192_000.0,
    "non_current_liabilities": 315_313_000.0,
    "total_equity": 1_281_310_000.0,
    "revenue": 805_925_000.0,
    "cost_of_sales": 603_314_000.0,
    "gross_profit": 202_611_000.0,
    "operating_cash_flow": 193_337_000.0,
    "investing_cash_flow": -4_499_000.0,
    "financing_cash_flow": -45_659_000.0,
    "net_change_in_cash": 139_906_000.0,
}


class TestTheBalanceSheet:
    def test_hilans_sheet_balances(self) -> None:
        assert check_balance_sheet_total(HILAN).holds
        assert check_balance_sheet(HILAN).holds

    def test_an_unbalanced_sheet_is_caught(self) -> None:
        broken = {**HILAN, "equity_and_liabilities": 2_900_000_000.0}

        assert check_balance_sheet_total(broken).outcome is IdentityOutcome.BROKEN


class TestGrossProfit:
    def test_hilans_gross_profit_reconciles(self) -> None:
        assert check_gross_profit(HILAN).holds

    def test_cost_of_sales_tagged_negative_still_reconciles(self) -> None:
        """Taking the sign on trust would turn a healthy margin into nonsense
        for any issuer that tags the cost as a negative magnitude."""
        flipped = {**HILAN, "cost_of_sales": -603_314_000.0}

        assert check_gross_profit(flipped).holds


class TestTheCashBridge:
    def test_the_exchange_rate_term_closes_the_bridge(self) -> None:
        """Hilan's gap was never an error. It is the reconciling line, and the
        company filed it — we had simply not mapped it."""
        check = check_cash_bridge({**HILAN, "effect_of_exchange_rate_on_cash": -3_273_000.0})

        assert check.outcome is IdentityOutcome.HOLDS
        assert check.unreported_terms == ()

    def test_an_absent_exchange_rate_term_is_recorded_not_assumed_zero(self) -> None:
        """Non-negotiable 1: unknown is never zero. The check still runs, and
        names the missing term so a gap carries its likely reason rather than
        reading as a flat accusation."""
        check = check_cash_bridge(HILAN)

        assert check.outcome is IdentityOutcome.BROKEN
        assert check.unreported_terms == ("effect_of_exchange_rate_on_cash",)

    def test_a_sign_convention_read_backwards_is_caught(self) -> None:
        """What decision 0010 said this check exists to find. A financing
        outflow stored positive still looks plausible on its own."""
        flipped = {
            **HILAN,
            "investing_cash_flow": 4_499_000.0,
            "financing_cash_flow": 45_659_000.0,
            "effect_of_exchange_rate_on_cash": -3_273_000.0,
        }

        assert check_cash_bridge(flipped).outcome is IdentityOutcome.BROKEN

    def test_a_domestic_company_with_no_exchange_effect_still_holds(self) -> None:
        closing = {
            **HILAN,
            "net_change_in_cash": 143_179_000.0,
        }
        check = check_cash_bridge(closing)

        assert check.outcome is IdentityOutcome.HOLDS


class TestNotCheckableIsNotAFailure:
    def test_a_bank_without_a_current_split_is_not_checkable(self) -> None:
        """US GAAP does not require the split and every American bank omits it.
        Counting that as a breach would condemn a sector for reporting exactly
        as its standard permits."""
        bank = {"total_assets": 3_499_191_000_000.0, "equity_and_liabilities": 3_499_191_000_000.0}
        check = check_balance_sheet(bank)

        assert check.outcome is IdentityOutcome.NOT_CHECKABLE
        assert "current_liabilities" in check.missing

    def test_an_issuer_reporting_by_nature_is_not_checkable_on_gross_profit(self) -> None:
        """62% of American issuers present no gross profit line at all."""
        assert check_gross_profit({"revenue": 805_925_000.0}).outcome is (
            IdentityOutcome.NOT_CHECKABLE
        )

    def test_a_not_checkable_identity_reports_no_difference(self) -> None:
        assert check_gross_profit({}).relative_difference is None


class TestRounding:
    """The bound is half a percent, which is what filings tagged to the nearest
    thousand can differ by once several are summed."""

    def test_rounding_at_the_tagged_granularity_is_not_a_breach(self) -> None:
        assert within_tolerance(2_972_815_000.0, 2_972_815_400.0)

    def test_a_gap_inside_half_a_percent_is_still_rounding(self) -> None:
        # 0.43% -- large in absolute terms on a balance sheet this size, and
        # still within what summing rounded figures produces.
        assert within_tolerance(2_972_815_000.0, 2_960_000_000.0)

    def test_a_real_gap_survives_the_tolerance(self) -> None:
        # 2.4%, which is Hilan's unreconciled cash bridge.
        assert not within_tolerance(2_972_815_000.0, 2_900_000_000.0)

    def test_two_figures_of_nothing_do_not_divide_by_zero(self) -> None:
        assert within_tolerance(0.0, 0.0)


class TestRunningThemTogether:
    def test_every_identity_runs(self) -> None:
        checks = check_all({**HILAN, "effect_of_exchange_rate_on_cash": -3_273_000.0})

        assert len(checks) == 4
        assert all(check.holds for check in checks)

    def test_names_are_unique_and_descriptive(self) -> None:
        names = [check.name for check in check_all(HILAN)]

        assert len(names) == len(set(names))
        assert all("_" in name for name in names)

    @pytest.mark.parametrize("figures", [{}, {"total_assets": 1.0}])
    def test_sparse_figures_produce_no_breaches(self, figures: dict[str, float]) -> None:
        assert all(check.outcome is IdentityOutcome.NOT_CHECKABLE for check in check_all(figures))
