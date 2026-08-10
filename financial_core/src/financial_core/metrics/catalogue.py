"""The canonical vocabulary of reported line items.

Codes are English so that adding a second market needs no schema migration;
display names are localised (spec section 45).

This file covers only what an issuer *reports*. Ratios and growth rates are
computed, and they arrive with the metric engine in phase 3 together with their
formulas and versions.

Two line items are deliberately kept apart rather than merged into a fallback
chain: total profit and profit attributable to owners are different amounts, and
so are total equity and equity attributable to owners. Treating one as a
substitute for the other would quietly change what a margin or a per-share
figure means when a company has minority interests.
"""

from dataclasses import dataclass
from enum import StrEnum
from typing import Final


class MetricCategory(StrEnum):
    """The dimension a line item belongs to (spec section 6.1)."""

    INCOME = "income"
    CASH_FLOW = "cash_flow"
    WORKING_CAPITAL = "working_capital"
    BALANCE_SHEET = "balance_sheet"
    SOLVENCY = "solvency"
    SHAREHOLDER = "shareholder"


class UnitType(StrEnum):
    """What kind of quantity a metric is, which decides how it is formatted."""

    CURRENCY = "currency"
    RATIO = "ratio"
    DAYS = "days"
    COUNT = "count"


@dataclass(frozen=True, slots=True)
class MetricSpec:
    """A canonical line item."""

    code: str
    name_he: str
    name_en: str
    category: MetricCategory
    unit_type: UnitType
    is_core: bool = True
    note: str | None = None


REPORTED_METRICS: Final[tuple[MetricSpec, ...]] = (
    # -- income statement -------------------------------------------------
    MetricSpec("revenue", "הכנסות", "Revenue", MetricCategory.INCOME, UnitType.CURRENCY),
    MetricSpec(
        "cost_of_sales", "עלות המכר", "Cost of sales", MetricCategory.INCOME, UnitType.CURRENCY
    ),
    MetricSpec(
        "gross_profit", "רווח גולמי", "Gross profit", MetricCategory.INCOME, UnitType.CURRENCY
    ),
    MetricSpec(
        "operating_profit",
        "רווח תפעולי",
        "Operating profit",
        MetricCategory.INCOME,
        UnitType.CURRENCY,
    ),
    MetricSpec("net_income", "רווח נקי", "Net profit", MetricCategory.INCOME, UnitType.CURRENCY),
    MetricSpec(
        "net_income_attributable_to_owners",
        "רווח נקי המיוחס לבעלי המניות",
        "Net profit attributable to owners",
        MetricCategory.INCOME,
        UnitType.CURRENCY,
        note="Excludes minority interests. Not interchangeable with net_income.",
    ),
    MetricSpec(
        "finance_costs", "הוצאות מימון", "Finance costs", MetricCategory.INCOME, UnitType.CURRENCY
    ),
    MetricSpec(
        "income_tax_expense",
        "מסים על ההכנסה",
        "Tax expense",
        MetricCategory.INCOME,
        UnitType.CURRENCY,
    ),
    MetricSpec(
        "depreciation_amortisation",
        "פחת והפחתות",
        "Depreciation and amortisation",
        MetricCategory.INCOME,
        UnitType.CURRENCY,
    ),
    # -- cash flow --------------------------------------------------------
    MetricSpec(
        "operating_cash_flow",
        "תזרים מפעילות שוטפת",
        "Operating cash flow",
        MetricCategory.CASH_FLOW,
        UnitType.CURRENCY,
    ),
    MetricSpec(
        "capital_expenditure",
        "השקעות ברכוש קבוע",
        "Capital expenditure",
        MetricCategory.CASH_FLOW,
        UnitType.CURRENCY,
    ),
    # -- working capital --------------------------------------------------
    MetricSpec(
        "trade_receivables",
        "לקוחות",
        "Trade receivables",
        MetricCategory.WORKING_CAPITAL,
        UnitType.CURRENCY,
        note="Trade only. Other receivables are excluded, or DSO is overstated.",
    ),
    MetricSpec(
        "trade_payables",
        "ספקים",
        "Trade payables",
        MetricCategory.WORKING_CAPITAL,
        UnitType.CURRENCY,
    ),
    MetricSpec(
        "inventories", "מלאי", "Inventories", MetricCategory.WORKING_CAPITAL, UnitType.CURRENCY
    ),
    # -- balance sheet ----------------------------------------------------
    MetricSpec(
        "total_assets", "סך נכסים", "Total assets", MetricCategory.BALANCE_SHEET, UnitType.CURRENCY
    ),
    MetricSpec(
        "current_assets",
        "נכסים שוטפים",
        "Current assets",
        MetricCategory.BALANCE_SHEET,
        UnitType.CURRENCY,
    ),
    MetricSpec(
        "current_liabilities",
        "התחייבויות שוטפות",
        "Current liabilities",
        MetricCategory.BALANCE_SHEET,
        UnitType.CURRENCY,
    ),
    MetricSpec(
        "non_current_liabilities",
        "התחייבויות לא שוטפות",
        "Non-current liabilities",
        MetricCategory.BALANCE_SHEET,
        UnitType.CURRENCY,
    ),
    MetricSpec(
        "cash_and_equivalents",
        "מזומנים ושווי מזומנים",
        "Cash and cash equivalents",
        MetricCategory.BALANCE_SHEET,
        UnitType.CURRENCY,
    ),
    MetricSpec(
        "total_equity", "סך ההון", "Total equity", MetricCategory.BALANCE_SHEET, UnitType.CURRENCY
    ),
    MetricSpec(
        "equity_attributable_to_owners",
        "הון המיוחס לבעלי המניות",
        "Equity attributable to owners",
        MetricCategory.BALANCE_SHEET,
        UnitType.CURRENCY,
        note="Excludes minority interests. Not interchangeable with total_equity.",
    ),
    # -- solvency ---------------------------------------------------------
    MetricSpec(
        "short_term_debt",
        "חוב לזמן קצר",
        "Short-term debt",
        MetricCategory.SOLVENCY,
        UnitType.CURRENCY,
        is_core=False,
        note="Sparsely tagged. Net debt and interest coverage are null without it.",
    ),
    MetricSpec(
        "long_term_debt",
        "חוב לזמן ארוך",
        "Long-term debt",
        MetricCategory.SOLVENCY,
        UnitType.CURRENCY,
        is_core=False,
        note="Sparsely tagged.",
    ),
    # -- shareholder ------------------------------------------------------
    MetricSpec(
        "weighted_average_shares_basic",
        "מספר מניות משוקלל בסיסי",
        "Weighted average shares, basic",
        MetricCategory.SHAREHOLDER,
        UnitType.COUNT,
        is_core=False,
        note="Sparsely tagged. Dilution is null without it.",
    ),
    MetricSpec(
        "weighted_average_shares_diluted",
        "מספר מניות משוקלל מדולל",
        "Weighted average shares, diluted",
        MetricCategory.SHAREHOLDER,
        UnitType.COUNT,
        is_core=False,
        note="Sparsely tagged.",
    ),
)

METRICS_BY_CODE: Final[dict[str, MetricSpec]] = {spec.code: spec for spec in REPORTED_METRICS}
