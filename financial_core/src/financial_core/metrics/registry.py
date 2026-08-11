"""The formula registry.

Spec section 33 requires every analytical rule to be versioned, so that a figure
computed last quarter can still be explained by the rule that produced it. The
registry is that record: one entry per computed metric, carrying its formula, its
version and what it means.

Adding a metric means adding an entry here. Changing what a formula *means*
means a new version, not an edit in place.
"""

from collections.abc import Callable, Sequence
from dataclasses import dataclass
from typing import Final

from financial_core.metrics import formulas
from financial_core.metrics.catalogue import MetricCategory, MetricTier, UnitType
from financial_core.metrics.results import MetricResult
from financial_core.metrics.values import FactSet
from financial_core.periods import DurationKind, FiscalPeriod

Formula = Callable[[FactSet, FiscalPeriod], MetricResult]


@dataclass(frozen=True, slots=True)
class CalculatedMetricSpec:
    """A metric the engine computes, as opposed to one an issuer reports."""

    code: str
    name_he: str
    name_en: str
    category: MetricCategory
    unit_type: UnitType
    formula: Formula
    formula_version: str = formulas.FORMULA_VERSION
    tier: MetricTier = MetricTier.EXTENDED
    """CORE means every input is a concept all issuers tag, so the metric works
    for every company with no per-issuer handling."""
    requires_quarter: bool = False
    """True when the metric is only defined on a discrete quarter."""
    note: str | None = None

    @property
    def is_core(self) -> bool:
        return self.tier is MetricTier.CORE

    def compute(self, facts: FactSet, period: FiscalPeriod) -> MetricResult:
        return self.formula(facts, period)


CALCULATED_METRICS: Final[tuple[CalculatedMetricSpec, ...]] = (
    # -- growth -----------------------------------------------------------
    CalculatedMetricSpec(
        "revenue_growth_yoy",
        "צמיחת הכנסות",
        "Revenue growth YoY",
        MetricCategory.INCOME,
        UnitType.RATIO,
        formulas.revenue_growth_yoy,
    ),
    CalculatedMetricSpec(
        "gross_profit_growth_yoy",
        "צמיחת רווח גולמי",
        "Gross profit growth YoY",
        MetricCategory.INCOME,
        UnitType.RATIO,
        formulas.gross_profit_growth_yoy,
    ),
    CalculatedMetricSpec(
        "operating_profit_growth_yoy",
        "צמיחת רווח תפעולי",
        "Operating profit growth YoY",
        MetricCategory.INCOME,
        UnitType.RATIO,
        formulas.operating_profit_growth_yoy,
        note="Null when the prior-year base is at or below zero; see the absolute change.",
    ),
    CalculatedMetricSpec(
        "net_income_growth_yoy",
        "צמיחת רווח נקי",
        "Net profit growth YoY",
        MetricCategory.INCOME,
        UnitType.RATIO,
        formulas.net_income_growth_yoy,
        tier=MetricTier.CORE,
    ),
    # -- margins ----------------------------------------------------------
    CalculatedMetricSpec(
        "gross_margin",
        "מרווח גולמי",
        "Gross margin",
        MetricCategory.INCOME,
        UnitType.RATIO,
        formulas.gross_margin,
    ),
    CalculatedMetricSpec(
        "operating_margin",
        "מרווח תפעולי",
        "Operating margin",
        MetricCategory.INCOME,
        UnitType.RATIO,
        formulas.operating_margin,
    ),
    CalculatedMetricSpec(
        "net_margin",
        "מרווח נקי",
        "Net margin",
        MetricCategory.INCOME,
        UnitType.RATIO,
        formulas.net_margin,
    ),
    CalculatedMetricSpec(
        "gross_margin_change_pp",
        "שינוי במרווח הגולמי",
        "Gross margin change",
        MetricCategory.INCOME,
        UnitType.RATIO,
        formulas.gross_margin_change_pp,
        note="Percentage points, not percent (spec section 13.2).",
    ),
    CalculatedMetricSpec(
        "operating_margin_change_pp",
        "שינוי במרווח התפעולי",
        "Operating margin change",
        MetricCategory.INCOME,
        UnitType.RATIO,
        formulas.operating_margin_change_pp,
    ),
    CalculatedMetricSpec(
        "net_margin_change_pp",
        "שינוי במרווח הנקי",
        "Net margin change",
        MetricCategory.INCOME,
        UnitType.RATIO,
        formulas.net_margin_change_pp,
    ),
    # -- cash -------------------------------------------------------------
    CalculatedMetricSpec(
        "free_cash_flow",
        "תזרים מזומנים חופשי",
        "Free cash flow",
        MetricCategory.CASH_FLOW,
        UnitType.CURRENCY,
        formulas.free_cash_flow,
        note="System definition: operating cash flow less capex. Not an IFRS measure.",
    ),
    CalculatedMetricSpec(
        "free_cash_flow_margin",
        "שיעור תזרים חופשי",
        "Free cash flow margin",
        MetricCategory.CASH_FLOW,
        UnitType.RATIO,
        formulas.free_cash_flow_margin,
    ),
    CalculatedMetricSpec(
        "cash_conversion",
        "המרת רווח למזומן",
        "Cash conversion",
        MetricCategory.CASH_FLOW,
        UnitType.RATIO,
        formulas.cash_conversion,
        tier=MetricTier.CORE,
        note="Null unless trailing net income is positive and material.",
    ),
    CalculatedMetricSpec(
        "accruals_proxy",
        "מדד צבירות",
        "Accruals proxy",
        MetricCategory.CASH_FLOW,
        UnitType.RATIO,
        formulas.accruals_proxy,
        tier=MetricTier.CORE,
        note="A signal only. Never evidence of manipulation (spec section 13.3).",
    ),
    # -- working capital --------------------------------------------------
    CalculatedMetricSpec(
        "days_sales_outstanding",
        "ימי גבייה מלקוחות",
        "Days sales outstanding",
        MetricCategory.WORKING_CAPITAL,
        UnitType.DAYS,
        formulas.days_sales_outstanding,
        requires_quarter=True,
    ),
    CalculatedMetricSpec(
        "days_inventory_outstanding",
        "ימי מלאי",
        "Days inventory outstanding",
        MetricCategory.WORKING_CAPITAL,
        UnitType.DAYS,
        formulas.days_inventory_outstanding,
        requires_quarter=True,
    ),
    CalculatedMetricSpec(
        "days_payables_outstanding",
        "ימי אשראי ספקים",
        "Days payables outstanding",
        MetricCategory.WORKING_CAPITAL,
        UnitType.DAYS,
        formulas.days_payables_outstanding,
        requires_quarter=True,
    ),
    CalculatedMetricSpec(
        "cash_conversion_cycle",
        "מחזור המרה למזומן",
        "Cash conversion cycle",
        MetricCategory.WORKING_CAPITAL,
        UnitType.DAYS,
        formulas.cash_conversion_cycle,
        requires_quarter=True,
    ),
    CalculatedMetricSpec(
        "receivables_growth_gap",
        "פער צמיחת לקוחות",
        "Receivables growth gap",
        MetricCategory.WORKING_CAPITAL,
        UnitType.RATIO,
        formulas.receivables_growth_gap,
        note="Percentage points. A difference, not a ratio of growth rates.",
    ),
    CalculatedMetricSpec(
        "inventory_growth_gap",
        "פער צמיחת מלאי",
        "Inventory growth gap",
        MetricCategory.WORKING_CAPITAL,
        UnitType.RATIO,
        formulas.inventory_growth_gap,
    ),
    # -- solvency ---------------------------------------------------------
    CalculatedMetricSpec(
        "net_debt",
        "חוב פיננסי נטו",
        "Net debt",
        MetricCategory.SOLVENCY,
        UnitType.CURRENCY,
        formulas.net_debt,
        note="Sparsely available: debt is thinly tagged.",
    ),
    CalculatedMetricSpec(
        "quick_ratio",
        "יחס מהיר",
        "Quick ratio",
        MetricCategory.SOLVENCY,
        UnitType.RATIO,
        formulas.quick_ratio,
        tier=MetricTier.CORE,
    ),
    CalculatedMetricSpec(
        "short_term_debt_share",
        "שיעור חוב לזמן קצר",
        "Short-term debt share",
        MetricCategory.SOLVENCY,
        UnitType.RATIO,
        formulas.short_term_debt_share,
    ),
    CalculatedMetricSpec(
        "interest_coverage",
        "כיסוי הוצאות מימון",
        "Interest coverage",
        MetricCategory.SOLVENCY,
        UnitType.RATIO,
        formulas.interest_coverage,
        note="Never evidence of a covenant breach without a stated covenant.",
    ),
    # -- efficiency and shareholder ---------------------------------------
    CalculatedMetricSpec(
        "asset_turnover",
        "מחזוריות נכסים",
        "Asset turnover",
        MetricCategory.BALANCE_SHEET,
        UnitType.RATIO,
        formulas.asset_turnover,
    ),
    CalculatedMetricSpec(
        "dilution_yoy",
        "דילול",
        "Dilution YoY",
        MetricCategory.SHAREHOLDER,
        UnitType.RATIO,
        formulas.dilution_yoy,
        note="Sparsely available: share counts are thinly tagged.",
    ),
    # -- tier one: works for every company --------------------------------
    CalculatedMetricSpec(
        "profit_before_tax_growth_yoy",
        "צמיחת רווח לפני מס",
        "Profit before tax growth YoY",
        MetricCategory.INCOME,
        UnitType.RATIO,
        formulas.profit_before_tax_growth_yoy,
        tier=MetricTier.CORE,
    ),
    CalculatedMetricSpec(
        "operating_cash_flow_growth_yoy",
        "צמיחת תזרים מפעילות שוטפת",
        "Operating cash flow growth YoY",
        MetricCategory.CASH_FLOW,
        UnitType.RATIO,
        formulas.operating_cash_flow_growth_yoy,
        tier=MetricTier.CORE,
    ),
    CalculatedMetricSpec(
        "effective_tax_rate",
        "שיעור מס אפקטיבי",
        "Effective tax rate",
        MetricCategory.INCOME,
        UnitType.RATIO,
        formulas.effective_tax_rate,
        tier=MetricTier.CORE,
        note="Null against a pre-tax loss, where the ratio inverts.",
    ),
    CalculatedMetricSpec(
        "net_finance_cost",
        "עלות מימון נטו",
        "Net finance cost",
        MetricCategory.INCOME,
        UnitType.CURRENCY,
        formulas.net_finance_cost,
        tier=MetricTier.CORE,
    ),
    CalculatedMetricSpec(
        "working_capital",
        "הון חוזר",
        "Working capital",
        MetricCategory.WORKING_CAPITAL,
        UnitType.CURRENCY,
        formulas.working_capital,
        tier=MetricTier.CORE,
        note="Negative is normal in some retail models, and is never scored.",
    ),
    CalculatedMetricSpec(
        "current_ratio",
        "יחס שוטף",
        "Current ratio",
        MetricCategory.BALANCE_SHEET,
        UnitType.RATIO,
        formulas.current_ratio,
        tier=MetricTier.CORE,
    ),
    CalculatedMetricSpec(
        "equity_ratio",
        "יחס הון למאזן",
        "Equity ratio",
        MetricCategory.BALANCE_SHEET,
        UnitType.RATIO,
        formulas.equity_ratio,
        tier=MetricTier.CORE,
    ),
    CalculatedMetricSpec(
        "liabilities_to_equity",
        "מינוף",
        "Liabilities to equity",
        MetricCategory.SOLVENCY,
        UnitType.RATIO,
        formulas.liabilities_to_equity,
        tier=MetricTier.CORE,
    ),
    CalculatedMetricSpec(
        "cash_runway_quarters",
        "מסלול מזומן ברבעונים",
        "Cash runway, quarters",
        MetricCategory.CASH_FLOW,
        UnitType.COUNT,
        formulas.cash_runway_quarters,
        tier=MetricTier.CORE,
        note="Only defined while operating cash flow is negative.",
    ),
)

CALCULATED_BY_CODE: Final[dict[str, CalculatedMetricSpec]] = {
    spec.code: spec for spec in CALCULATED_METRICS
}


def compute_all(facts: FactSet, period: FiscalPeriod) -> dict[str, MetricResult]:
    """Every metric that applies to a period.

    Metrics defined only on a discrete quarter are skipped for cumulative
    periods rather than computed and quietly wrong.
    """
    is_quarter = period.duration_kind is DurationKind.QUARTER
    return {
        spec.code: spec.compute(facts, period)
        for spec in CALCULATED_METRICS
        if is_quarter or not spec.requires_quarter
    }


def series(facts: FactSet, metric_code: str, periods: Sequence[FiscalPeriod]) -> list[MetricResult]:
    """One metric across many periods, oldest first."""
    spec = CALCULATED_BY_CODE[metric_code]
    return [spec.compute(facts, period) for period in sorted(periods)]
