"""MAGNA concept chains, version 1.

Every chain below was measured, not guessed. On 2026-08-09 the thirty candidate
concepts were queried across all thirty-nine reporting entities for 2022-2025,
and the counts in the comments are how many entities actually reported each one.

Two rules decide the order:

1. **Precision before availability.** The concept that means exactly what the
   metric means comes first, even when a broader one is more widely tagged. A
   number that is quietly measuring something else is worse than a null.
2. **Availability breaks ties** between concepts that mean the same thing.

The receivables chain is why decision 0009 exists. `TradeAndOtherCurrentReceivables`
-- the obvious choice, and the one used in the phase 1 probe -- is reported by
eleven entities. `CurrentTradeReceivables` is reported by thirty-one, and is the
more precise concept as well. Mapping to a single standard tag would have left
DSO null for most of the market.

`ifrs-full:OtherCurrentReceivables` is deliberately absent despite being the most
widely tagged receivables concept of all, at thirty-six entities. It is *other*
receivables -- prepayments, tax and sundry debtors -- and folding it into trade
receivables would inflate DSO for almost every company.
"""

from typing import Final

MAPPING_VERSION: Final[str] = "v1"
PROVIDER_CODE_DEFAULT: Final[str] = "magna_xbrl"

# metric code -> raw concepts, most precise first.
CONCEPT_CHAINS: Final[dict[str, tuple[str, ...]]] = {
    # -- income statement -------------------------------------------------
    "revenue": ("ifrs-full:Revenue",),
    "cost_of_sales": ("ifrs-full:CostOfSales",),
    "gross_profit": ("ifrs-full:GrossProfit",),
    "operating_profit": ("ifrs-full:ProfitLossFromOperatingActivities",),  # 32
    "net_income": ("ifrs-full:ProfitLoss",),  # 39
    "net_income_attributable_to_owners": (
        "ifrs-full:ProfitLossAttributableToOwnersOfParent",
    ),  # 33
    "finance_costs": ("ifrs-full:FinanceCosts",),
    "income_tax_expense": ("ifrs-full:IncomeTaxExpenseContinuingOperations",),
    "depreciation_amortisation": (
        # The expense as reported in profit and loss is the primary meaning; the
        # cash flow add-back is the same amount reached another way, and is far
        # more widely tagged.
        "ifrs-full:DepreciationAndAmortisationExpense",  # 4
        "ifrs-full:AdjustmentsForDepreciationAndAmortisationExpense",  # 28
    ),
    # -- cash flow --------------------------------------------------------
    "operating_cash_flow": (
        "ifrs-full:CashFlowsFromUsedInOperatingActivities",
        "ifrs-full:CashFlowsFromUsedInOperatingActivitiesContinuingOperations",
    ),
    "capital_expenditure": (
        "ifrs-full:PurchaseOfPropertyPlantAndEquipmentClassifiedAsInvestingActivities",
        # Broader: bundles intangibles and investment property with PP&E. Usable,
        # but it overstates maintenance capex, so it comes second.
        "ifrs-full:PurchaseOfPropertyPlantAndEquipmentIntangibleAssetsOtherThanGoodwill"
        "InvestmentPropertyAndOtherNoncurrentAssets",
    ),
    # -- working capital --------------------------------------------------
    "trade_receivables": (
        "ifrs-full:CurrentTradeReceivables",  # 31, and the most precise
        "ifrs-full:TradeReceivables",  # 6
        "ifrs-full:CurrentReceivablesFromContractsWithCustomers",  # 1
    ),
    # The payables equivalent of the receivables trap, and it resolves the other
    # way. `TradeAndOtherCurrentPayables` is used as the *smaller* line by only
    # 2 of the 7 issuers that tag both, and 8 issuers tag nothing else -- so
    # dropping it would cost real coverage to guard against a minority reading.
    # It stays behind the supplier-specific concept, which wins wherever both
    # exist. A DPO of a very few days is the symptom to watch for.
    "trade_payables": (
        "ifrs-full:TradeAndOtherCurrentPayablesToTradeSuppliers",  # 23, trade only
        "ifrs-full:TradeAndOtherCurrentPayables",  # 15
        "ifrs-full:TradeAndOtherPayables",  # 5
    ),
    "inventories": (
        "ifrs-full:Inventories",  # 24
        "ifrs-full:InventoriesTotal",  # 6
    ),
    # -- balance sheet ----------------------------------------------------
    "total_assets": ("ifrs-full:Assets",),
    "current_assets": ("ifrs-full:CurrentAssets",),
    "current_liabilities": ("ifrs-full:CurrentLiabilities",),  # 39
    "non_current_liabilities": ("ifrs-full:NoncurrentLiabilities",),  # 39
    "cash_and_equivalents": ("ifrs-full:CashAndCashEquivalents",),
    "total_equity": ("ifrs-full:Equity",),  # 39
    "equity_attributable_to_owners": ("ifrs-full:EquityAttributableToOwnersOfParent",),  # 32
    # -- solvency ---------------------------------------------------------
    # Thinly tagged across the board. Net debt, net debt to EBITDA and interest
    # coverage will be null for most companies, and that is the honest answer
    # rather than a number assembled from whatever was to hand.
    "short_term_debt": (
        "ifrs-full:ShorttermBorrowings",  # 7
        "ifrs-full:CurrentPortionOfLongtermBorrowings",  # 2
        "ifrs-full:OtherCurrentBorrowingsAndCurrentPortionOfOtherNoncurrentBorrowings",  # 2
        "ifrs-full:CurrentBorrowingsAndCurrentPortionOfNoncurrentBorrowings",  # 1
    ),
    "long_term_debt": ("ifrs-full:LongtermBorrowings",),  # 8
    # -- shareholder ------------------------------------------------------
    "weighted_average_shares_basic": ("ifrs-full:WeightedAverageShares",),  # 3
    "weighted_average_shares_diluted": ("ifrs-full:AdjustedWeightedAverageShares",),  # 4
}

# Concepts that look like a match and are not. Kept explicit so nobody adds them
# back after noticing how widely they are tagged.
DELIBERATELY_EXCLUDED: Final[dict[str, str]] = {
    "ifrs-full:OtherCurrentReceivables": (
        "reported by 36 of 39 entities, but it is non-trade receivables; "
        "including it would inflate DSO for almost every company"
    ),
    "ifrs-full:TradeAndOtherCurrentReceivables": (
        "the label says trade AND other, so it ought to be a superset of trade "
        "receivables. Measured against issuers that tag both, 6 of 7 use it for "
        "the much smaller 'other receivables' line instead: Matrix IT tags "
        "1,746,539,000 as CurrentTradeReceivables and 113,123,000 here. Using it "
        "as a fallback would understate DSO by an order of magnitude. Only four "
        "entities rely on it alone, and all four are outside the MVP universe"
    ),
    "ifrs-full:TradeAndOtherReceivables": (
        "same ambiguity, and no entity relies on it alone, so it adds risk "
        "without adding a single company's coverage"
    ),
    "ifrs-full:Liabilities": (
        "total liabilities, tagged by only 13 entities; current and non-current "
        "are tagged by all 39 and sum to the same thing"
    ),
}


def all_mapped_concepts() -> tuple[str, ...]:
    """Every raw concept any chain refers to, for building a provider query."""
    return tuple(dict.fromkeys(concept for chain in CONCEPT_CHAINS.values() for concept in chain))
