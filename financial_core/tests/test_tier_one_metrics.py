"""Tier one metrics: the ones that must work for every company.

Every input these use is a concept tagged by 100% of issuers, so a failure here
is a failure for the whole market rather than for one awkward filer. The tests
therefore lean on the refusal cases: a pre-tax loss, negative equity, a company
generating cash rather than burning it.
"""

import pytest

from financial_core.metrics import FactPoint, FactSet
from financial_core.metrics.catalogue import MetricTier
from financial_core.metrics.formulas import (
    cash_runway_quarters,
    current_ratio,
    effective_tax_rate,
    equity_ratio,
    liabilities_to_equity,
    net_finance_cost,
    working_capital,
)
from financial_core.metrics.registry import CALCULATED_METRICS
from financial_core.metrics.results import MetricWarning
from financial_core.periods import PeriodKind, classify_instant, discrete_period, quarter_end

QUARTER = discrete_period(2024, 3)


def facts_from(**figures: float) -> FactSet:
    """Build a fact set, putting balance sheet items on the quarter-end instant."""
    balance_codes = {
        "current_assets",
        "current_liabilities",
        "non_current_liabilities",
        "total_assets",
        "total_equity",
        "cash_and_equivalents",
        "inventories",
    }
    instant = classify_instant(quarter_end(QUARTER.fiscal_year, QUARTER.fiscal_quarter))
    assert instant is not None

    points = []
    for code, value in figures.items():
        period = instant if code in balance_codes else QUARTER
        points.append(FactPoint(code, period, value, f"ifrs-full:{code}"))
    return FactSet(points)


# -- effective tax rate ---------------------------------------------------


def test_effective_tax_rate_on_a_profit() -> None:
    facts = facts_from(profit_before_tax=100_000_000, income_tax_expense=23_000_000)

    result = effective_tax_rate(facts, QUARTER)

    assert result.value == pytest.approx(0.23)


def test_effective_tax_rate_handles_a_tax_expense_tagged_negative() -> None:
    """Sign conventions differ between issuers; the magnitude is what matters."""
    facts = facts_from(profit_before_tax=100_000_000, income_tax_expense=-23_000_000)

    assert effective_tax_rate(facts, QUARTER).value == pytest.approx(0.23)


def test_effective_tax_rate_is_null_against_a_pre_tax_loss() -> None:
    """Against a loss the ratio inverts and a tax benefit reads as a burden."""
    facts = facts_from(profit_before_tax=-40_000_000, income_tax_expense=5_000_000)

    result = effective_tax_rate(facts, QUARTER)

    assert result.value is None
    assert MetricWarning.NEGATIVE_DENOMINATOR in result.warnings


# -- net finance cost -----------------------------------------------------


def test_net_finance_cost_nets_both_sides() -> None:
    """A company can carry large gross costs and larger gross income."""
    facts = facts_from(finance_costs=30_000_000, finance_income=42_000_000)

    result = net_finance_cost(facts, QUARTER)

    assert result.value == pytest.approx(-12_000_000)


def test_net_finance_cost_needs_both_sides() -> None:
    facts = facts_from(finance_costs=30_000_000)

    result = net_finance_cost(facts, QUARTER)

    assert result.value is None
    assert result.missing_inputs == ("finance_income",)


# -- liquidity and capital structure --------------------------------------


def test_working_capital_can_be_negative_without_complaint() -> None:
    """Spec section 18: negative working capital is normal in some retail
    models, so it is reported and never scored."""
    facts = facts_from(current_assets=800_000_000, current_liabilities=950_000_000)

    result = working_capital(facts, QUARTER)

    assert result.value == pytest.approx(-150_000_000)
    assert not result.warnings


def test_current_ratio() -> None:
    facts = facts_from(current_assets=2_515_922_000, current_liabilities=2_370_000_000)

    assert current_ratio(facts, QUARTER).value == pytest.approx(1.0616, abs=1e-4)


def test_current_ratio_is_null_without_current_liabilities() -> None:
    facts = facts_from(current_assets=800_000_000, current_liabilities=0)

    result = current_ratio(facts, QUARTER)

    assert result.value is None
    assert MetricWarning.NEGATIVE_DENOMINATOR in result.warnings


def test_equity_ratio() -> None:
    facts = facts_from(total_equity=1_600_000_000, total_assets=4_094_300_000)

    assert equity_ratio(facts, QUARTER).value == pytest.approx(0.3908, abs=1e-4)


def test_leverage_comes_from_the_accounting_identity() -> None:
    """Total liabilities is a thinly tagged subtotal -- a third of Israeli
    issuers and 66% of American ones -- so it is reached as assets less equity.
    Both of those are tagged by every issuer in both markets."""
    facts = facts_from(
        total_assets=4_100_000_000,
        total_equity=1_600_000_000,
    )

    assert liabilities_to_equity(facts, QUARTER).value == pytest.approx(1.5625)


def test_leverage_resolves_without_a_current_liability_split() -> None:
    """US GAAP does not require one. A bank orders its balance sheet by
    liquidity and tags neither half, and this metric must still resolve."""
    facts = facts_from(total_assets=4_100_000_000, total_equity=1_600_000_000)

    assert liabilities_to_equity(facts, QUARTER).value is not None


def test_leverage_is_null_on_negative_equity() -> None:
    """A negative denominator makes the ratio meaningless, not merely large."""
    facts = facts_from(
        total_assets=2_400_000_000,
        total_equity=-100_000_000,
    )

    result = liabilities_to_equity(facts, QUARTER)

    assert result.value is None
    assert MetricWarning.NEGATIVE_DENOMINATOR in result.warnings


# -- cash runway ----------------------------------------------------------


def test_cash_runway_is_null_for_a_company_generating_cash() -> None:
    """There is no runway to measure, and a number would invite the wrong read."""
    points = [
        FactPoint("operating_cash_flow", discrete_period(2024, q), 50_000_000, "ifrs-full:ocf")
        for q in (1, 2, 3)
    ]
    points.append(
        FactPoint("operating_cash_flow", discrete_period(2023, 4), 50_000_000, "ifrs-full:ocf")
    )
    instant = classify_instant(quarter_end(2024, 3))
    assert instant is not None
    points.append(FactPoint("cash_and_equivalents", instant, 500_000_000, "ifrs-full:cash"))

    result = cash_runway_quarters(FactSet(points), QUARTER)

    assert result.value is None
    assert MetricWarning.IMMATERIAL_DENOMINATOR in result.warnings


def test_cash_runway_counts_quarters_of_burn() -> None:
    points = [
        FactPoint("operating_cash_flow", discrete_period(2024, q), -25_000_000, "ifrs-full:ocf")
        for q in (1, 2, 3)
    ]
    points.append(
        FactPoint("operating_cash_flow", discrete_period(2023, 4), -25_000_000, "ifrs-full:ocf")
    )
    instant = classify_instant(quarter_end(2024, 3))
    assert instant is not None
    points.append(FactPoint("cash_and_equivalents", instant, 200_000_000, "ifrs-full:cash"))

    result = cash_runway_quarters(FactSet(points), QUARTER)

    assert result.value == pytest.approx(8.0)


# -- the tier itself ------------------------------------------------------


def test_every_core_metric_resolves_from_universal_line_items_alone() -> None:
    """This is what CORE means, asserted directly.

    Revenue is tagged by 86% of issuers, gross profit by 69%, inventories by 62%.
    Given only the concepts every issuer tags, every core metric must still
    produce a figure -- otherwise it is not core, whatever the label says.
    """
    universal = facts_from(
        net_income=100.0,
        profit_before_tax=130.0,
        income_tax_expense=30.0,
        finance_costs=10.0,
        finance_income=4.0,
        total_assets=1000.0,
        current_assets=600.0,
        current_liabilities=400.0,
        non_current_liabilities=200.0,
        total_equity=400.0,
        cash_and_equivalents=150.0,
        operating_cash_flow=90.0,
    )

    needs_history = {
        "net_income_growth_yoy",
        "profit_before_tax_growth_yoy",
        "operating_cash_flow_growth_yoy",
        "cash_conversion",
        "accruals_proxy",
        "cash_runway_quarters",
    }

    for spec in CALCULATED_METRICS:
        if spec.tier is not MetricTier.CORE or spec.code in needs_history:
            continue
        result = spec.compute(universal, QUARTER)
        assert result.is_available, (
            f"core metric {spec.code} could not resolve from universal line items; "
            f"missing {result.missing_inputs}"
        )


def test_every_core_metric_input_is_a_core_line_item() -> None:
    from financial_core.metrics import CORE_LINE_ITEMS

    assert "revenue" not in CORE_LINE_ITEMS
    assert "gross_profit" not in CORE_LINE_ITEMS
    assert {"net_income", "total_assets", "operating_cash_flow", "total_equity"} <= set(
        CORE_LINE_ITEMS
    )


def test_balance_items_live_on_instants() -> None:
    facts = facts_from(total_assets=1000.0)
    instant = classify_instant(quarter_end(2024, 3))

    assert instant is not None
    assert instant.period_kind is PeriodKind.INSTANT
    assert facts.value("total_assets", instant) == 1000.0
