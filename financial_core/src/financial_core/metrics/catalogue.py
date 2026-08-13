"""The canonical vocabulary of reported line items.

Codes are English so that adding a second market needs no schema migration;
display names are localised (spec section 45).

This file covers only what an issuer *reports*. Ratios and growth rates are
computed, and they live in the registry with their formulas and versions.

## Tiers

Measured across every entity that filed in 2024, not assumed. Seventeen concepts
are tagged by **all** of them; the rest are not, and some are not merely untagged
but genuinely absent — an issuer presenting profit or loss by nature has no gross
profit line to tag.

`CORE` metrics rest only on concepts every issuer reports, so a metric built from
them works for every company with no per-issuer handling. `EXTENDED` metrics rest
on concepts that are common but not guaranteed; they resolve where the data
exists and are `null` where it does not, with no special-casing either way.

Two figures worth knowing before reading the tiers:

* **Revenue is tagged by 86% of issuers, not all.** Financial companies report
  interest and fee income instead. Every revenue-based metric is EXTENDED.
* **Gross profit is tagged by 69%.** Presentation by nature rather than by
  function leaves no such line. It will never be a universal metric.

Two line items are deliberately kept apart rather than merged into a fallback
chain: total profit and profit attributable to owners are different amounts, and
so are total equity and equity attributable to owners. Treating one as a
substitute for the other would quietly change what a margin or a per-share
figure means when a company has minority interests.
"""

from dataclasses import dataclass
from enum import StrEnum
from typing import Final


class MetricTier(StrEnum):
    """How dependable a metric's inputs are across the market."""

    CORE = "core"
    """Rests only on concepts every issuer tags. Works for every company."""

    EXTENDED = "extended"
    """Rests on concepts that are common but not universal."""


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
    tier: MetricTier = MetricTier.EXTENDED
    coverage: int | None = None
    """Percentage of issuers tagging this concept, as measured in 2024."""
    note: str | None = None

    @property
    def is_core(self) -> bool:
        return self.tier is MetricTier.CORE


def _core(
    code: str,
    name_he: str,
    name_en: str,
    category: MetricCategory,
    unit_type: UnitType = UnitType.CURRENCY,
    coverage: int = 100,
    note: str | None = None,
) -> MetricSpec:
    return MetricSpec(code, name_he, name_en, category, unit_type, MetricTier.CORE, coverage, note)


def _extended(
    code: str,
    name_he: str,
    name_en: str,
    category: MetricCategory,
    unit_type: UnitType = UnitType.CURRENCY,
    coverage: int | None = None,
    note: str | None = None,
) -> MetricSpec:
    return MetricSpec(
        code, name_he, name_en, category, unit_type, MetricTier.EXTENDED, coverage, note
    )


REPORTED_METRICS: Final[tuple[MetricSpec, ...]] = (
    # ================= tier one: tagged by every issuer =================
    # -- profit or loss ---------------------------------------------------
    _core("net_income", "רווח נקי", "Net profit", MetricCategory.INCOME),
    _core("profit_before_tax", "רווח לפני מס", "Profit before tax", MetricCategory.INCOME),
    _core("income_tax_expense", "מסים על ההכנסה", "Tax expense", MetricCategory.INCOME),
    _core("finance_costs", "הוצאות מימון", "Finance costs", MetricCategory.INCOME),
    _core("finance_income", "הכנסות מימון", "Finance income", MetricCategory.INCOME),
    _core("comprehensive_income", "רווח כולל", "Comprehensive income", MetricCategory.INCOME),
    # -- financial position ----------------------------------------------
    _core("total_assets", "סך נכסים", "Total assets", MetricCategory.BALANCE_SHEET),
    _core("current_assets", "נכסים שוטפים", "Current assets", MetricCategory.BALANCE_SHEET),
    _core(
        "non_current_assets", "נכסים לא שוטפים", "Non-current assets", MetricCategory.BALANCE_SHEET
    ),
    _core(
        "current_liabilities",
        "התחייבויות שוטפות",
        "Current liabilities",
        MetricCategory.BALANCE_SHEET,
    ),
    _core(
        "non_current_liabilities",
        "התחייבויות לא שוטפות",
        "Non-current liabilities",
        MetricCategory.BALANCE_SHEET,
    ),
    _core("total_equity", "סך ההון", "Total equity", MetricCategory.BALANCE_SHEET),
    _core(
        "equity_and_liabilities",
        "סך ההון וההתחייבויות",
        "Equity and liabilities",
        MetricCategory.BALANCE_SHEET,
        note="The other side of the balance sheet identity.",
    ),
    _core(
        "cash_and_equivalents",
        "מזומנים ושווי מזומנים",
        "Cash and cash equivalents",
        MetricCategory.BALANCE_SHEET,
    ),
    # -- cash flow --------------------------------------------------------
    _core(
        "operating_cash_flow",
        "תזרים מפעילות שוטפת",
        "Operating cash flow",
        MetricCategory.CASH_FLOW,
    ),
    _core(
        "investing_cash_flow",
        "תזרים מפעילות השקעה",
        "Investing cash flow",
        MetricCategory.CASH_FLOW,
    ),
    _core(
        "financing_cash_flow",
        "תזרים מפעילות מימון",
        "Financing cash flow",
        MetricCategory.CASH_FLOW,
    ),
    # ================= tier two: common, not guaranteed =================
    _extended(
        "net_change_in_cash",
        "שינוי במזומנים",
        "Net change in cash",
        MetricCategory.CASH_FLOW,
        coverage=97,
    ),
    _extended(
        "effect_of_exchange_rate_on_cash",
        "השפעת שער חליפין על מזומנים",
        "Effect of exchange rates on cash",
        MetricCategory.CASH_FLOW,
        coverage=74,
        note="The reconciling line between the three cash flow subtotals and the "
        "change in the cash balance. Without it the cash bridge does not close "
        "for any company holding cash abroad, which is most of them.",
    ),
    _extended(
        "property_plant_equipment",
        "רכוש קבוע",
        "Property, plant and equipment",
        MetricCategory.BALANCE_SHEET,
        coverage=97,
    ),
    _extended(
        "trade_receivables",
        "לקוחות",
        "Trade receivables",
        MetricCategory.WORKING_CAPITAL,
        coverage=90,
        note="Trade only. Other receivables are excluded, or DSO is overstated.",
    ),
    _extended(
        "revenue",
        "הכנסות",
        "Revenue",
        MetricCategory.INCOME,
        coverage=86,
        note="Financial companies report interest and fee income instead.",
    ),
    _extended(
        "operating_profit", "רווח תפעולי", "Operating profit", MetricCategory.INCOME, coverage=86
    ),
    _extended(
        "net_income_attributable_to_owners",
        "רווח נקי המיוחס לבעלי המניות",
        "Net profit attributable to owners",
        MetricCategory.INCOME,
        coverage=83,
        note="Excludes minority interests. Not interchangeable with net_income.",
    ),
    _extended(
        "equity_attributable_to_owners",
        "הון המיוחס לבעלי המניות",
        "Equity attributable to owners",
        MetricCategory.BALANCE_SHEET,
        coverage=83,
        note="Excludes minority interests. Not interchangeable with total_equity.",
    ),
    _extended(
        "capital_expenditure",
        "השקעות ברכוש קבוע",
        "Capital expenditure",
        MetricCategory.CASH_FLOW,
        coverage=76,
    ),
    _extended(
        "depreciation_amortisation",
        "פחת והפחתות",
        "Depreciation and amortisation",
        MetricCategory.INCOME,
        coverage=72,
    ),
    _extended("cost_of_sales", "עלות המכר", "Cost of sales", MetricCategory.INCOME, coverage=72),
    _extended(
        "gross_profit",
        "רווח גולמי",
        "Gross profit",
        MetricCategory.INCOME,
        coverage=69,
        note="Absent entirely when profit or loss is presented by nature.",
    ),
    _extended(
        "trade_payables", "ספקים", "Trade payables", MetricCategory.WORKING_CAPITAL, coverage=69
    ),
    _extended("inventories", "מלאי", "Inventories", MetricCategory.WORKING_CAPITAL, coverage=62),
    # ================= tier three: thin =================================
    _extended(
        "short_term_debt",
        "חוב לזמן קצר",
        "Short-term debt",
        MetricCategory.SOLVENCY,
        coverage=18,
        note="Net debt and interest coverage are null without it.",
    ),
    _extended(
        "long_term_debt", "חוב לזמן ארוך", "Long-term debt", MetricCategory.SOLVENCY, coverage=21
    ),
    _extended(
        "weighted_average_shares_basic",
        "מספר מניות משוקלל בסיסי",
        "Weighted average shares, basic",
        MetricCategory.SHAREHOLDER,
        UnitType.COUNT,
        coverage=8,
    ),
    _extended(
        "weighted_average_shares_diluted",
        "מספר מניות משוקלל מדולל",
        "Weighted average shares, diluted",
        MetricCategory.SHAREHOLDER,
        UnitType.COUNT,
        coverage=10,
    ),
)

METRICS_BY_CODE: Final[dict[str, MetricSpec]] = {spec.code: spec for spec in REPORTED_METRICS}

CORE_LINE_ITEMS: Final[tuple[str, ...]] = tuple(
    spec.code for spec in REPORTED_METRICS if spec.is_core
)
