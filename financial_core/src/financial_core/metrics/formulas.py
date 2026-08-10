"""The deterministic metric formulas.

Every rule the spec states about arithmetic is enforced here rather than
documented and hoped for:

* Growth against a base at or below zero is not a percentage (section 13.1). The
  absolute change and the loss-to-profit crossing are reported instead.
* Margin movements are percentage points, not percent (section 13.2).
* Cash conversion is meaningless when the denominator is small or negative
  (section 13.3).
* A ratio mixing a balance with a flow averages the balance, and uses the real
  number of days in the period (section 13.4).
* Receivables and inventory pressure are growth *gaps* in percentage points, not
  ratios of growth rates, which are unstable near zero (section 13.4).

A figure that cannot be computed correctly comes back as `None` with a warning.
"""

from financial_core.metrics.aggregation import (
    average_balance,
    balance_at,
    days_in,
    is_discrete_quarter,
    trailing_twelve_months,
)
from financial_core.metrics.catalogue import UnitType
from financial_core.metrics.results import MetricResult, MetricWarning
from financial_core.metrics.values import FactSet
from financial_core.periods import FiscalPeriod

FORMULA_VERSION = "v1"

# Below this share of trailing revenue, trailing net income is too small for a
# ratio built on it to carry meaning (spec section 13.3 requires materiality but
# does not set a level). Provisional: see docs/financial-methodology.md.
CASH_CONVERSION_MATERIALITY = 0.01


def _result(
    code: str,
    period: FiscalPeriod,
    value: float | None,
    unit_type: UnitType,
    inputs: dict[str, float | None],
    *,
    detail: dict[str, float] | None = None,
    warnings: tuple[MetricWarning, ...] = (),
) -> MetricResult:
    return MetricResult(
        code=code,
        period=period,
        value=value,
        unit_type=unit_type,
        formula_version=FORMULA_VERSION,
        inputs=inputs,
        detail=detail or {},
        warnings=warnings,
    )


def _margin(code: str, numerator_code: str, facts: FactSet, period: FiscalPeriod) -> MetricResult:
    """A share of revenue, expressed as a fraction."""
    numerator = facts.value(numerator_code, period)
    revenue = facts.value("revenue", period)
    inputs = {numerator_code: numerator, "revenue": revenue}

    if numerator is None or revenue is None:
        return _result(
            code, period, None, UnitType.RATIO, inputs, warnings=(MetricWarning.MISSING_INPUT,)
        )
    if revenue <= 0:
        # A margin on zero or negative revenue is not a margin.
        return _result(
            code,
            period,
            None,
            UnitType.RATIO,
            inputs,
            warnings=(MetricWarning.NEGATIVE_DENOMINATOR,),
        )

    return _result(code, period, numerator / revenue, UnitType.RATIO, inputs)


def gross_margin(facts: FactSet, period: FiscalPeriod) -> MetricResult:
    return _margin("gross_margin", "gross_profit", facts, period)


def operating_margin(facts: FactSet, period: FiscalPeriod) -> MetricResult:
    return _margin("operating_margin", "operating_profit", facts, period)


def net_margin(facts: FactSet, period: FiscalPeriod) -> MetricResult:
    return _margin("net_margin", "net_income", facts, period)


def _growth_yoy(code: str, metric_code: str, facts: FactSet, period: FiscalPeriod) -> MetricResult:
    """Year-on-year growth, or an honest refusal.

    Spec section 13.1: when the base is at or below zero a percentage is
    misleading, sometimes wildly. The change in currency and the fact of crossing
    zero are reported instead, and the ratio is null.
    """
    prior_period = period.previous_year()
    current = facts.value(metric_code, period)
    base = facts.value(metric_code, prior_period)
    inputs = {f"{metric_code}_current": current, f"{metric_code}_prior": base}

    if current is None or base is None:
        return _result(
            code, period, None, UnitType.RATIO, inputs, warnings=(MetricWarning.MISSING_INPUT,)
        )

    detail = {"current": current, "prior": base, "absolute_change": current - base}

    warnings: tuple[MetricWarning, ...]
    if base <= 0:
        warnings = (MetricWarning.NON_POSITIVE_BASE,)
        if base < 0 < current:
            warnings = (*warnings, MetricWarning.CROSSED_ZERO)
        return _result(code, period, None, UnitType.RATIO, inputs, detail=detail, warnings=warnings)

    warnings = (MetricWarning.CROSSED_ZERO,) if current < 0 else ()
    return _result(
        code,
        period,
        (current / base) - 1.0,
        UnitType.RATIO,
        inputs,
        detail=detail,
        warnings=warnings,
    )


def revenue_growth_yoy(facts: FactSet, period: FiscalPeriod) -> MetricResult:
    return _growth_yoy("revenue_growth_yoy", "revenue", facts, period)


def gross_profit_growth_yoy(facts: FactSet, period: FiscalPeriod) -> MetricResult:
    return _growth_yoy("gross_profit_growth_yoy", "gross_profit", facts, period)


def operating_profit_growth_yoy(facts: FactSet, period: FiscalPeriod) -> MetricResult:
    return _growth_yoy("operating_profit_growth_yoy", "operating_profit", facts, period)


def net_income_growth_yoy(facts: FactSet, period: FiscalPeriod) -> MetricResult:
    return _growth_yoy("net_income_growth_yoy", "net_income", facts, period)


def _margin_change_pp(
    code: str, margin_fn: object, facts: FactSet, period: FiscalPeriod
) -> MetricResult:
    """Movement in a margin, in percentage points.

    Spec section 13.2: 9.1% to 10.0% is +0.9pp, not +9.9%. Reporting it as a
    percentage of a percentage is the classic way to overstate a small move.
    """
    assert callable(margin_fn)
    current = margin_fn(facts, period)
    prior = margin_fn(facts, period.previous_year())
    inputs = {"margin_current": current.value, "margin_prior": prior.value}

    if current.value is None or prior.value is None:
        return _result(
            code, period, None, UnitType.RATIO, inputs, warnings=(MetricWarning.MISSING_INPUT,)
        )

    return _result(code, period, (current.value - prior.value) * 100.0, UnitType.RATIO, inputs)


def gross_margin_change_pp(facts: FactSet, period: FiscalPeriod) -> MetricResult:
    return _margin_change_pp("gross_margin_change_pp", gross_margin, facts, period)


def operating_margin_change_pp(facts: FactSet, period: FiscalPeriod) -> MetricResult:
    return _margin_change_pp("operating_margin_change_pp", operating_margin, facts, period)


def net_margin_change_pp(facts: FactSet, period: FiscalPeriod) -> MetricResult:
    return _margin_change_pp("net_margin_change_pp", net_margin, facts, period)


def free_cash_flow(facts: FactSet, period: FiscalPeriod) -> MetricResult:
    """Operating cash flow less capital expenditure.

    This is a system definition, not an IFRS measure, and must be labelled as one
    wherever it is shown (spec section 13.3). Capital expenditure is tagged as a
    positive magnitude, so its absolute value is subtracted.
    """
    ocf = facts.value("operating_cash_flow", period)
    capex = facts.value("capital_expenditure", period)
    inputs = {"operating_cash_flow": ocf, "capital_expenditure": capex}

    if ocf is None or capex is None:
        return _result(
            "free_cash_flow",
            period,
            None,
            UnitType.CURRENCY,
            inputs,
            warnings=(MetricWarning.MISSING_INPUT,),
        )
    return _result("free_cash_flow", period, ocf - abs(capex), UnitType.CURRENCY, inputs)


def free_cash_flow_margin(facts: FactSet, period: FiscalPeriod) -> MetricResult:
    fcf = free_cash_flow(facts, period)
    revenue = facts.value("revenue", period)
    inputs = {"free_cash_flow": fcf.value, "revenue": revenue}

    if fcf.value is None or revenue is None:
        return _result(
            "free_cash_flow_margin",
            period,
            None,
            UnitType.RATIO,
            inputs,
            warnings=(MetricWarning.MISSING_INPUT,),
        )
    if revenue <= 0:
        return _result(
            "free_cash_flow_margin",
            period,
            None,
            UnitType.RATIO,
            inputs,
            warnings=(MetricWarning.NEGATIVE_DENOMINATOR,),
        )
    return _result("free_cash_flow_margin", period, fcf.value / revenue, UnitType.RATIO, inputs)


def cash_conversion(facts: FactSet, period: FiscalPeriod) -> MetricResult:
    """Trailing operating cash flow over trailing net income.

    Only meaningful when trailing net income is positive and material. A small or
    negative denominator produces a ratio that reads as the opposite of what it
    is, so the answer is null with a warning instead (spec section 13.3).
    """
    ocf = trailing_twelve_months(facts, "operating_cash_flow", period)
    net_income = trailing_twelve_months(facts, "net_income", period)
    revenue = trailing_twelve_months(facts, "revenue", period)
    inputs = {
        "operating_cash_flow_ttm": None if ocf is None else ocf.value,
        "net_income_ttm": None if net_income is None else net_income.value,
    }

    if ocf is None or net_income is None:
        return _result(
            "cash_conversion",
            period,
            None,
            UnitType.RATIO,
            inputs,
            warnings=(MetricWarning.MISSING_INPUT,),
        )
    if net_income.value <= 0:
        return _result(
            "cash_conversion",
            period,
            None,
            UnitType.RATIO,
            inputs,
            warnings=(MetricWarning.NEGATIVE_DENOMINATOR,),
        )
    immaterial = (
        revenue is not None
        and revenue.value > 0
        and net_income.value < CASH_CONVERSION_MATERIALITY * revenue.value
    )
    if immaterial:
        return _result(
            "cash_conversion",
            period,
            None,
            UnitType.RATIO,
            inputs,
            warnings=(MetricWarning.IMMATERIAL_DENOMINATOR,),
        )

    return _result("cash_conversion", period, ocf.value / net_income.value, UnitType.RATIO, inputs)


def accruals_proxy(facts: FactSet, period: FiscalPeriod) -> MetricResult:
    """Trailing net income less trailing operating cash flow, over average assets.

    A signal only. Spec section 13.3 is explicit that this must never be
    translated into an accusation of manipulation.
    """
    net_income = trailing_twelve_months(facts, "net_income", period)
    ocf = trailing_twelve_months(facts, "operating_cash_flow", period)
    assets, averaged = average_balance(facts, "total_assets", period)
    inputs = {
        "net_income_ttm": None if net_income is None else net_income.value,
        "operating_cash_flow_ttm": None if ocf is None else ocf.value,
        "average_total_assets": assets,
    }

    if net_income is None or ocf is None or assets is None:
        return _result(
            "accruals_proxy",
            period,
            None,
            UnitType.RATIO,
            inputs,
            warnings=(MetricWarning.MISSING_INPUT,),
        )
    if assets <= 0:
        return _result(
            "accruals_proxy",
            period,
            None,
            UnitType.RATIO,
            inputs,
            warnings=(MetricWarning.NEGATIVE_DENOMINATOR,),
        )

    warnings = () if averaged else (MetricWarning.SINGLE_PERIOD,)
    return _result(
        "accruals_proxy",
        period,
        (net_income.value - ocf.value) / assets,
        UnitType.RATIO,
        inputs,
        warnings=warnings,
    )


def _days_ratio(
    code: str, balance_code: str, flow_code: str, facts: FactSet, period: FiscalPeriod
) -> MetricResult:
    """A balance expressed as days of a flow.

    Only defined on a discrete quarter: a year-to-date flow against a quarter-end
    balance would silently mix period lengths (spec section 14.6).
    """
    balance, averaged = average_balance(facts, balance_code, period)
    flow = facts.value(flow_code, period)
    inputs = {f"average_{balance_code}": balance, flow_code: flow}

    if not is_discrete_quarter(period):
        return _result(
            code, period, None, UnitType.DAYS, inputs, warnings=(MetricWarning.MISSING_INPUT,)
        )
    if balance is None or flow is None:
        return _result(
            code, period, None, UnitType.DAYS, inputs, warnings=(MetricWarning.MISSING_INPUT,)
        )
    if flow <= 0:
        return _result(
            code,
            period,
            None,
            UnitType.DAYS,
            inputs,
            warnings=(MetricWarning.NEGATIVE_DENOMINATOR,),
        )

    warnings = () if averaged else (MetricWarning.SINGLE_PERIOD,)
    return _result(
        code, period, balance / flow * days_in(period), UnitType.DAYS, inputs, warnings=warnings
    )


def days_sales_outstanding(facts: FactSet, period: FiscalPeriod) -> MetricResult:
    return _days_ratio("days_sales_outstanding", "trade_receivables", "revenue", facts, period)


def days_inventory_outstanding(facts: FactSet, period: FiscalPeriod) -> MetricResult:
    return _days_ratio("days_inventory_outstanding", "inventories", "cost_of_sales", facts, period)


def days_payables_outstanding(facts: FactSet, period: FiscalPeriod) -> MetricResult:
    return _days_ratio(
        "days_payables_outstanding", "trade_payables", "cost_of_sales", facts, period
    )


def cash_conversion_cycle(facts: FactSet, period: FiscalPeriod) -> MetricResult:
    dso = days_sales_outstanding(facts, period)
    dio = days_inventory_outstanding(facts, period)
    dpo = days_payables_outstanding(facts, period)
    inputs = {
        "days_sales_outstanding": dso.value,
        "days_inventory_outstanding": dio.value,
        "days_payables_outstanding": dpo.value,
    }

    if dso.value is None or dio.value is None or dpo.value is None:
        return _result(
            "cash_conversion_cycle",
            period,
            None,
            UnitType.DAYS,
            inputs,
            warnings=(MetricWarning.MISSING_INPUT,),
        )
    return _result(
        "cash_conversion_cycle", period, dso.value + dio.value - dpo.value, UnitType.DAYS, inputs
    )


def _growth_gap(code: str, balance_code: str, facts: FactSet, period: FiscalPeriod) -> MetricResult:
    """Balance growth less revenue growth, in percentage points.

    Spec section 13.4 replaces the ratio of the two growth rates, which explodes
    when revenue growth approaches zero, with their difference.
    """
    prior_period = period.previous_year()
    balance_now = balance_at(facts, balance_code, period)
    balance_then = balance_at(facts, balance_code, prior_period)
    revenue_now = facts.value("revenue", period)
    revenue_then = facts.value("revenue", prior_period)
    inputs = {
        f"{balance_code}_current": balance_now,
        f"{balance_code}_prior": balance_then,
        "revenue_current": revenue_now,
        "revenue_prior": revenue_then,
    }

    if None in (balance_now, balance_then, revenue_now, revenue_then):
        return _result(
            code, period, None, UnitType.RATIO, inputs, warnings=(MetricWarning.MISSING_INPUT,)
        )
    assert balance_now is not None and balance_then is not None
    assert revenue_now is not None and revenue_then is not None

    if balance_then <= 0 or revenue_then <= 0:
        return _result(
            code, period, None, UnitType.RATIO, inputs, warnings=(MetricWarning.NON_POSITIVE_BASE,)
        )

    balance_growth = (balance_now / balance_then) - 1.0
    revenue_growth = (revenue_now / revenue_then) - 1.0
    detail = {"balance_growth": balance_growth, "revenue_growth": revenue_growth}
    return _result(
        code,
        period,
        (balance_growth - revenue_growth) * 100.0,
        UnitType.RATIO,
        inputs,
        detail=detail,
    )


def receivables_growth_gap(facts: FactSet, period: FiscalPeriod) -> MetricResult:
    return _growth_gap("receivables_growth_gap", "trade_receivables", facts, period)


def inventory_growth_gap(facts: FactSet, period: FiscalPeriod) -> MetricResult:
    return _growth_gap("inventory_growth_gap", "inventories", facts, period)


def net_debt(facts: FactSet, period: FiscalPeriod) -> MetricResult:
    """Interest bearing debt less cash."""
    short_term = balance_at(facts, "short_term_debt", period)
    long_term = balance_at(facts, "long_term_debt", period)
    cash = balance_at(facts, "cash_and_equivalents", period)
    inputs = {
        "short_term_debt": short_term,
        "long_term_debt": long_term,
        "cash_and_equivalents": cash,
    }

    if short_term is None or long_term is None or cash is None:
        return _result(
            "net_debt",
            period,
            None,
            UnitType.CURRENCY,
            inputs,
            warnings=(MetricWarning.MISSING_INPUT,),
        )
    return _result("net_debt", period, short_term + long_term - cash, UnitType.CURRENCY, inputs)


def quick_ratio(facts: FactSet, period: FiscalPeriod) -> MetricResult:
    """Current assets excluding inventory, over current liabilities."""
    current_assets = balance_at(facts, "current_assets", period)
    inventories = balance_at(facts, "inventories", period)
    current_liabilities = balance_at(facts, "current_liabilities", period)
    inputs = {
        "current_assets": current_assets,
        "inventories": inventories,
        "current_liabilities": current_liabilities,
    }

    if current_assets is None or current_liabilities is None:
        return _result(
            "quick_ratio",
            period,
            None,
            UnitType.RATIO,
            inputs,
            warnings=(MetricWarning.MISSING_INPUT,),
        )
    if current_liabilities <= 0:
        return _result(
            "quick_ratio",
            period,
            None,
            UnitType.RATIO,
            inputs,
            warnings=(MetricWarning.NEGATIVE_DENOMINATOR,),
        )

    # A company with no inventory reports none; treating that as unknown would
    # make the ratio null for every service business.
    stock = inventories or 0.0
    return _result(
        "quick_ratio",
        period,
        (current_assets - stock) / current_liabilities,
        UnitType.RATIO,
        inputs,
    )


def short_term_debt_share(facts: FactSet, period: FiscalPeriod) -> MetricResult:
    short_term = balance_at(facts, "short_term_debt", period)
    long_term = balance_at(facts, "long_term_debt", period)
    inputs = {"short_term_debt": short_term, "long_term_debt": long_term}

    if short_term is None or long_term is None:
        return _result(
            "short_term_debt_share",
            period,
            None,
            UnitType.RATIO,
            inputs,
            warnings=(MetricWarning.MISSING_INPUT,),
        )
    total = short_term + long_term
    if total <= 0:
        return _result(
            "short_term_debt_share",
            period,
            None,
            UnitType.RATIO,
            inputs,
            warnings=(MetricWarning.IMMATERIAL_DENOMINATOR,),
        )
    return _result("short_term_debt_share", period, short_term / total, UnitType.RATIO, inputs)


def interest_coverage(facts: FactSet, period: FiscalPeriod) -> MetricResult:
    """Trailing operating profit over trailing finance costs.

    Spec section 13.5: a weak reading is a weak reading. It is never evidence of
    a covenant breach unless the filing states a covenant to compare against.
    """
    ebit = trailing_twelve_months(facts, "operating_profit", period)
    finance = trailing_twelve_months(facts, "finance_costs", period)
    inputs = {
        "operating_profit_ttm": None if ebit is None else ebit.value,
        "finance_costs_ttm": None if finance is None else finance.value,
    }

    if ebit is None or finance is None:
        return _result(
            "interest_coverage",
            period,
            None,
            UnitType.RATIO,
            inputs,
            warnings=(MetricWarning.MISSING_INPUT,),
        )
    cost = abs(finance.value)
    if cost <= 0:
        return _result(
            "interest_coverage",
            period,
            None,
            UnitType.RATIO,
            inputs,
            warnings=(MetricWarning.IMMATERIAL_DENOMINATOR,),
        )
    return _result("interest_coverage", period, ebit.value / cost, UnitType.RATIO, inputs)


def asset_turnover(facts: FactSet, period: FiscalPeriod) -> MetricResult:
    revenue = trailing_twelve_months(facts, "revenue", period)
    assets, averaged = average_balance(facts, "total_assets", period)
    inputs = {
        "revenue_ttm": None if revenue is None else revenue.value,
        "average_total_assets": assets,
    }

    if revenue is None or assets is None:
        return _result(
            "asset_turnover",
            period,
            None,
            UnitType.RATIO,
            inputs,
            warnings=(MetricWarning.MISSING_INPUT,),
        )
    if assets <= 0:
        return _result(
            "asset_turnover",
            period,
            None,
            UnitType.RATIO,
            inputs,
            warnings=(MetricWarning.NEGATIVE_DENOMINATOR,),
        )

    warnings = () if averaged else (MetricWarning.SINGLE_PERIOD,)
    return _result(
        "asset_turnover", period, revenue.value / assets, UnitType.RATIO, inputs, warnings=warnings
    )


def dilution_yoy(facts: FactSet, period: FiscalPeriod) -> MetricResult:
    """Change in the diluted share count, year on year."""
    return _growth_yoy("dilution_yoy", "weighted_average_shares_diluted", facts, period)
