"""Every formula, and every way it can go wrong.

Spec section 34 asks for the awkward cases explicitly: zero and negative
denominators, missing inputs, crossing zero, and mixing period kinds. Those are
the cases that produce a plausible-looking wrong number, so they get more
attention here than the happy path.
"""

import pytest

from financial_core.metrics import FactPoint, FactSet, MetricWarning
from financial_core.metrics import formulas as f
from financial_core.periods import (
    FiscalPeriod,
    PeriodKind,
    cumulative_period,
    discrete_period,
    quarter_end,
)


def instant(year: int, quarter: int) -> FiscalPeriod:
    return FiscalPeriod(
        fiscal_year=year,
        fiscal_quarter=quarter,
        period_kind=PeriodKind.INSTANT,
        duration_kind=None,
        end=quarter_end(year, quarter),
    )


def facts_from(**by_metric: dict[FiscalPeriod, float]) -> FactSet:
    return FactSet(
        FactPoint(metric_code=code, period=period, value=value, raw_concept=f"test:{code}")
        for code, series in by_metric.items()
        for period, value in series.items()
    )


Q3_2024 = discrete_period(2024, 3)
Q3_2023 = discrete_period(2023, 3)


# -- margins --------------------------------------------------------------


def test_gross_margin_normal_case() -> None:
    facts = facts_from(revenue={Q3_2024: 1000.0}, gross_profit={Q3_2024: 350.0})

    result = f.gross_margin(facts, Q3_2024)

    assert result.value == pytest.approx(0.35)
    assert not result.warnings


def test_a_margin_on_zero_revenue_is_null() -> None:
    facts = facts_from(revenue={Q3_2024: 0.0}, gross_profit={Q3_2024: 350.0})

    result = f.gross_margin(facts, Q3_2024)

    assert result.value is None
    assert MetricWarning.NEGATIVE_DENOMINATOR in result.warnings


def test_a_margin_on_negative_revenue_is_null() -> None:
    """A negative denominator would flip the sign and read as the opposite."""
    facts = facts_from(revenue={Q3_2024: -1000.0}, gross_profit={Q3_2024: 350.0})

    assert f.gross_margin(facts, Q3_2024).value is None


def test_a_margin_with_a_missing_input_names_what_is_missing() -> None:
    facts = facts_from(revenue={Q3_2024: 1000.0})

    result = f.gross_margin(facts, Q3_2024)

    assert result.value is None
    assert MetricWarning.MISSING_INPUT in result.warnings
    assert result.missing_inputs == ("gross_profit",)


def test_a_negative_margin_is_a_real_answer() -> None:
    """A loss-making quarter has a negative margin. That is not an error."""
    facts = facts_from(revenue={Q3_2024: 1000.0}, operating_profit={Q3_2024: -200.0})

    assert f.operating_margin(facts, Q3_2024).value == pytest.approx(-0.2)


# -- growth ---------------------------------------------------------------


def test_growth_normal_case() -> None:
    facts = facts_from(revenue={Q3_2023: 1000.0, Q3_2024: 1120.0})

    result = f.revenue_growth_yoy(facts, Q3_2024)

    assert result.value == pytest.approx(0.12)


def test_growth_from_a_negative_base_is_refused() -> None:
    """Spec section 13.1. A percentage against a loss is meaningless and often
    spectacular; the change in currency is reported instead."""
    facts = facts_from(operating_profit={Q3_2023: -50.0, Q3_2024: 100.0})

    result = f.operating_profit_growth_yoy(facts, Q3_2024)

    assert result.value is None
    assert MetricWarning.NON_POSITIVE_BASE in result.warnings
    assert MetricWarning.CROSSED_ZERO in result.warnings
    assert result.detail["absolute_change"] == pytest.approx(150.0)


def test_growth_from_a_zero_base_is_refused() -> None:
    facts = facts_from(revenue={Q3_2023: 0.0, Q3_2024: 500.0})

    result = f.revenue_growth_yoy(facts, Q3_2024)

    assert result.value is None
    assert MetricWarning.NON_POSITIVE_BASE in result.warnings


def test_falling_into_a_loss_is_flagged_even_though_the_ratio_computes() -> None:
    """Profit to loss is arithmetically -1.4, and that number hides the story."""
    facts = facts_from(operating_profit={Q3_2023: 100.0, Q3_2024: -40.0})

    result = f.operating_profit_growth_yoy(facts, Q3_2024)

    assert result.value == pytest.approx(-1.4)
    assert MetricWarning.CROSSED_ZERO in result.warnings


def test_growth_with_no_prior_year_is_null() -> None:
    facts = facts_from(revenue={Q3_2024: 1120.0})

    result = f.revenue_growth_yoy(facts, Q3_2024)

    assert result.value is None
    assert MetricWarning.MISSING_INPUT in result.warnings


# -- margin movement ------------------------------------------------------


def test_margin_change_is_percentage_points_not_percent() -> None:
    """9.1% to 10.0% is +0.9pp. Reported as a percent it would be +9.9%."""
    facts = facts_from(
        revenue={Q3_2023: 1000.0, Q3_2024: 1000.0},
        operating_profit={Q3_2023: 91.0, Q3_2024: 100.0},
    )

    result = f.operating_margin_change_pp(facts, Q3_2024)

    assert result.value == pytest.approx(0.9)


# -- trailing twelve months ----------------------------------------------


def four_quarters(**values: float) -> dict[FiscalPeriod, float]:
    quarters = [discrete_period(2023, 4), *(discrete_period(2024, q) for q in (1, 2, 3))]
    return dict(zip(quarters, values.values(), strict=True))


def test_cash_conversion_normal_case() -> None:
    facts = facts_from(
        operating_cash_flow=four_quarters(a=20.0, b=20.0, c=20.0, d=20.0),
        net_income=four_quarters(a=25.0, b=25.0, c=25.0, d=25.0),
        revenue=four_quarters(a=1000.0, b=1000.0, c=1000.0, d=1000.0),
    )

    result = f.cash_conversion(facts, Q3_2024)

    assert result.value == pytest.approx(0.8)


def test_a_trailing_metric_needs_four_quarters() -> None:
    """Three quarters and a gap is not a year, and must not be presented as one."""
    quarters = four_quarters(a=20.0, b=20.0, c=20.0, d=20.0)
    del quarters[discrete_period(2024, 1)]
    facts = facts_from(
        operating_cash_flow=quarters, net_income=four_quarters(a=25.0, b=25.0, c=25.0, d=25.0)
    )

    result = f.cash_conversion(facts, Q3_2024)

    assert result.value is None
    assert MetricWarning.MISSING_INPUT in result.warnings


def test_cash_conversion_is_null_when_trailing_profit_is_negative() -> None:
    """Dividing by a loss inverts the sign and reads as the opposite."""
    facts = facts_from(
        operating_cash_flow=four_quarters(a=20.0, b=20.0, c=20.0, d=20.0),
        net_income=four_quarters(a=-25.0, b=-25.0, c=-25.0, d=-25.0),
    )

    result = f.cash_conversion(facts, Q3_2024)

    assert result.value is None
    assert MetricWarning.NEGATIVE_DENOMINATOR in result.warnings


def test_cash_conversion_is_null_when_trailing_profit_is_immaterial() -> None:
    """A hair above break-even produces an enormous ratio that means nothing."""
    facts = facts_from(
        operating_cash_flow=four_quarters(a=20.0, b=20.0, c=20.0, d=20.0),
        net_income=four_quarters(a=0.1, b=0.1, c=0.1, d=0.1),
        revenue=four_quarters(a=1000.0, b=1000.0, c=1000.0, d=1000.0),
    )

    result = f.cash_conversion(facts, Q3_2024)

    assert result.value is None
    assert MetricWarning.IMMATERIAL_DENOMINATOR in result.warnings


# -- free cash flow -------------------------------------------------------


def test_free_cash_flow_subtracts_capex_regardless_of_its_sign() -> None:
    """Capex is tagged as a positive magnitude here and negative elsewhere.
    Taking the sign on trust would add it back instead of spending it."""
    positive = facts_from(operating_cash_flow={Q3_2024: 100.0}, capital_expenditure={Q3_2024: 30.0})
    negative = facts_from(
        operating_cash_flow={Q3_2024: 100.0}, capital_expenditure={Q3_2024: -30.0}
    )

    assert f.free_cash_flow(positive, Q3_2024).value == pytest.approx(70.0)
    assert f.free_cash_flow(negative, Q3_2024).value == pytest.approx(70.0)


# -- working capital ------------------------------------------------------


def test_dso_averages_the_balance_and_uses_real_days() -> None:
    """Q3 2024 has 92 days. Receivables average 200 against 1000 of revenue."""
    facts = FactSet(
        [
            FactPoint("revenue", Q3_2024, 1000.0, "test"),
            FactPoint("trade_receivables", instant(2024, 2), 150.0, "test"),
            FactPoint("trade_receivables", instant(2024, 3), 250.0, "test"),
        ]
    )

    result = f.days_sales_outstanding(facts, Q3_2024)

    assert result.value == pytest.approx(200.0 / 1000.0 * 92)
    assert not result.warnings


def test_dso_falls_back_to_the_closing_balance_and_says_so() -> None:
    facts = FactSet(
        [
            FactPoint("revenue", Q3_2024, 1000.0, "test"),
            FactPoint("trade_receivables", instant(2024, 3), 250.0, "test"),
        ]
    )

    result = f.days_sales_outstanding(facts, Q3_2024)

    assert result.value == pytest.approx(250.0 / 1000.0 * 92)
    assert MetricWarning.SINGLE_PERIOD in result.warnings


def test_dso_refuses_a_cumulative_period() -> None:
    """A nine-month flow against a quarter-end balance mixes period lengths,
    which spec section 14.6 forbids."""
    nine_months = cumulative_period(2024, 3)
    facts = FactSet(
        [
            FactPoint("revenue", nine_months, 3000.0, "test"),
            FactPoint("trade_receivables", instant(2024, 3), 250.0, "test"),
        ]
    )

    assert f.days_sales_outstanding(facts, nine_months).value is None


def test_growth_gap_is_a_difference_in_percentage_points() -> None:
    """Spec section 13.4 replaces the ratio of growth rates, which explodes when
    revenue growth nears zero, with their difference."""
    facts = FactSet(
        [
            FactPoint("revenue", Q3_2023, 1000.0, "test"),
            FactPoint("revenue", Q3_2024, 1080.0, "test"),
            FactPoint("trade_receivables", instant(2023, 3), 200.0, "test"),
            FactPoint("trade_receivables", instant(2024, 3), 250.0, "test"),
        ]
    )

    result = f.receivables_growth_gap(facts, Q3_2024)

    # receivables +25%, revenue +8% -> a gap of 17 percentage points
    assert result.value == pytest.approx(17.0)


def test_growth_gap_stays_finite_when_revenue_barely_moves() -> None:
    """The rejected ratio formulation would divide by 0.001 here."""
    facts = FactSet(
        [
            FactPoint("revenue", Q3_2023, 1000.0, "test"),
            FactPoint("revenue", Q3_2024, 1001.0, "test"),
            FactPoint("trade_receivables", instant(2023, 3), 200.0, "test"),
            FactPoint("trade_receivables", instant(2024, 3), 260.0, "test"),
        ]
    )

    result = f.receivables_growth_gap(facts, Q3_2024)

    assert result.value == pytest.approx(29.9)


# -- solvency -------------------------------------------------------------


def test_quick_ratio_treats_a_company_with_no_inventory_correctly() -> None:
    """A service business reports no inventory. Reading that as unknown would
    make the ratio null for an entire sector."""
    facts = FactSet(
        [
            FactPoint("current_assets", instant(2024, 3), 500.0, "test"),
            FactPoint("current_liabilities", instant(2024, 3), 250.0, "test"),
        ]
    )

    assert f.quick_ratio(facts, Q3_2024).value == pytest.approx(2.0)


def test_quick_ratio_excludes_inventory_when_there_is_some() -> None:
    facts = FactSet(
        [
            FactPoint("current_assets", instant(2024, 3), 500.0, "test"),
            FactPoint("inventories", instant(2024, 3), 100.0, "test"),
            FactPoint("current_liabilities", instant(2024, 3), 250.0, "test"),
        ]
    )

    assert f.quick_ratio(facts, Q3_2024).value == pytest.approx(1.6)


def test_net_debt_is_null_without_debt_tags() -> None:
    """Debt is thinly tagged. Null is the honest answer, not zero debt."""
    facts = FactSet([FactPoint("cash_and_equivalents", instant(2024, 3), 800.0, "test")])

    result = f.net_debt(facts, Q3_2024)

    assert result.value is None
    assert set(result.missing_inputs) == {"short_term_debt", "long_term_debt"}


def test_interest_coverage_handles_finance_costs_tagged_either_sign() -> None:
    quarters = [discrete_period(2023, 4), *(discrete_period(2024, q) for q in (1, 2, 3))]
    facts = FactSet(
        [FactPoint("operating_profit", q, 100.0, "test") for q in quarters]
        + [FactPoint("finance_costs", q, -10.0, "test") for q in quarters]
    )

    assert f.interest_coverage(facts, Q3_2024).value == pytest.approx(10.0)


def test_interest_coverage_is_null_with_no_finance_costs() -> None:
    quarters = [discrete_period(2023, 4), *(discrete_period(2024, q) for q in (1, 2, 3))]
    facts = FactSet(
        [FactPoint("operating_profit", q, 100.0, "test") for q in quarters]
        + [FactPoint("finance_costs", q, 0.0, "test") for q in quarters]
    )

    result = f.interest_coverage(facts, Q3_2024)

    assert result.value is None
    assert MetricWarning.IMMATERIAL_DENOMINATOR in result.warnings
