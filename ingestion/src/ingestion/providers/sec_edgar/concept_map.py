"""SEC EDGAR (`us-gaap`) concept chains, version 1.

Every chain below was measured, not guessed. Forty-seven American issuers were
surveyed across technology, retail, healthcare, energy, industrials, banking,
payments and telecoms, counting concepts with data since 2020. The percentages
in the comments are the share of those companies a chain resolves for.

The two ordering rules are decision 0009's, unchanged:

1. **Precision before availability.** The concept that means exactly what the
   metric means comes first, even when a broader one is more widely tagged.
2. **Availability breaks ties** between concepts that mean the same thing.

What the survey changed is the *tier*, and it is worth stating plainly:
**the American universal core is smaller than the Israeli one.** Only nine
`us-gaap` concepts are tagged by all forty-seven companies, against seventeen
IFRS concepts across the Israeli market.

The reason is the balance sheet. IFRS requires a current/non-current split;
US GAAP does not, and a bank presents an unclassified balance sheet ordered by
liquidity instead. JPMorgan, Morgan Stanley, Goldman Sachs and Bank of America
tag no `AssetsCurrent` and no `LiabilitiesCurrent` at all. Working capital, the
current ratio and the quick ratio therefore **cannot be CORE metrics in the
United States**, though decision 0010 made them CORE for Israel. They resolve
for the 89% who do present a classified balance sheet and are null elsewhere.

`GrossProfit` is worse here than in Israel: 38% against 69%. Amazon, Alphabet,
Costco, AT&T and every bank present no gross profit line. It was already barred
from Report Pulse; the American data makes that decision look generous.
"""

from typing import Final

MAPPING_VERSION: Final[str] = "v1"
PROVIDER_CODE_DEFAULT: Final[str] = "sec_edgar"

# metric code -> raw concepts, most precise first.
CONCEPT_CHAINS: Final[dict[str, tuple[str, ...]]] = {
    # -- income statement -------------------------------------------------
    # 100% only once the banks' presentation is included. A bank reports revenue
    # net of interest expense, which is its top line, not an operating subtotal.
    "revenue": (
        "us-gaap:RevenueFromContractWithCustomerExcludingAssessedTax",
        "us-gaap:Revenues",
        "us-gaap:RevenueFromContractWithCustomerIncludingAssessedTax",
        "us-gaap:RevenuesNetOfInterestExpense",  # banks
        "us-gaap:SalesRevenueNet",  # retired in 2018, still in older filings
    ),  # 100%
    "cost_of_sales": (
        "us-gaap:CostOfGoodsAndServicesSold",
        "us-gaap:CostOfRevenue",
        "us-gaap:CostOfGoodsSold",
        "us-gaap:CostOfServices",
    ),  # 70%
    "gross_profit": ("us-gaap:GrossProfit",),  # 38% -- see the module docstring
    "operating_profit": ("us-gaap:OperatingIncomeLoss",),  # 72%
    # `ProfitLoss` is the whole bottom line and `NetIncomeLoss` the portion
    # attributable to the parent -- but a company with no minority interest tags
    # only `NetIncomeLoss`, and means the whole thing by it. So the two concepts
    # both belong to `net_income`, most precise first.
    #
    # That leaves `net_income_attributable_to_owners` with no concept of its own,
    # and it is left null here rather than pointed at `NetIncomeLoss` as well.
    # The store enforces one concept to one metric, and rightly: a tag cannot
    # mean two different things at once. Under IFRS the split is two distinct
    # tags and the metric resolves; under US GAAP it is not reliably separable,
    # and null is the honest answer (section 4.4).
    "net_income": ("us-gaap:ProfitLoss", "us-gaap:NetIncomeLoss"),  # 100%
    "profit_before_tax": (
        "us-gaap:IncomeLossFromContinuingOperationsBeforeIncomeTaxesExtraordinaryItems"
        "NoncontrollingInterest",
        "us-gaap:IncomeLossFromContinuingOperationsBeforeIncomeTaxesMinorityInterest"
        "AndIncomeLossFromEquityMethodInvestments",
        "us-gaap:IncomeLossFromContinuingOperationsBeforeIncomeTaxesDomestic",
    ),  # 100%
    "income_tax_expense": ("us-gaap:IncomeTaxExpenseBenefit",),  # 100%
    "comprehensive_income": ("us-gaap:ComprehensiveIncomeNetOfTax",),  # 96%
    # `InterestExpense` is the total; the debt-specific and non-operating
    # variants are narrower readings that some issuers tag instead.
    "finance_costs": (
        "us-gaap:InterestExpense",
        "us-gaap:InterestExpenseNonoperating",
        "us-gaap:InterestExpenseDebt",
    ),  # 89%
    # Thin, and deliberately not padded. `InterestAndDividendIncomeOperating` is
    # a bank's operating revenue rather than a financing item, so it is excluded
    # even though including it would lift the number.
    "finance_income": (
        "us-gaap:InvestmentIncomeInterest",
        "us-gaap:InterestIncomeOperating",
    ),  # 55%
    "depreciation_amortisation": (
        "us-gaap:DepreciationDepletionAndAmortization",
        "us-gaap:DepreciationAmortizationAndAccretionNet",
        "us-gaap:Depreciation",
    ),  # 94%
    # -- cash flow --------------------------------------------------------
    "operating_cash_flow": (
        "us-gaap:NetCashProvidedByUsedInOperatingActivities",
        "us-gaap:NetCashProvidedByUsedInOperatingActivitiesContinuingOperations",
    ),  # 100%
    "investing_cash_flow": (
        "us-gaap:NetCashProvidedByUsedInInvestingActivities",
        "us-gaap:NetCashProvidedByUsedInInvestingActivitiesContinuingOperations",
    ),  # 100%
    "financing_cash_flow": (
        "us-gaap:NetCashProvidedByUsedInFinancingActivities",
        "us-gaap:NetCashProvidedByUsedInFinancingActivitiesContinuingOperations",
    ),  # 100%
    # ASU 2016-18 folded restricted cash into the cash flow statement's
    # reconciliation, so the long concept is the current one and the short is
    # the pre-2018 filing.
    "net_change_in_cash": (
        "us-gaap:CashCashEquivalentsRestrictedCashAndRestrictedCashEquivalents"
        "PeriodIncreaseDecreaseIncludingExchangeRateEffect",
        "us-gaap:CashAndCashEquivalentsPeriodIncreaseDecrease",
    ),  # 98%
    # The reconciling line the cash bridge needs. Without it the three cash flow
    # subtotals do not sum to the change in cash for any company holding money
    # abroad -- measured, that was 43 of 54 companies before this was mapped.
    #
    # The disposal-group variants matter more than their coverage suggests. Only
    # 21% tag one, but they are the *only* line Tesla, GE, Oracle, Goldman Sachs
    # and Honeywell file, so leaving them out left five companies looking as
    # though their cash flow statements did not add up.
    "effect_of_exchange_rate_on_cash": (
        "us-gaap:EffectOfExchangeRateOnCashCashEquivalentsRestrictedCash"
        "AndRestrictedCashEquivalents",  # 74%
        "us-gaap:EffectOfExchangeRateOnCashCashEquivalentsRestrictedCash"
        "AndRestrictedCashEquivalentsIncludingDisposalGroupAndDiscontinuedOperations",  # 21%
        "us-gaap:EffectOfExchangeRateOnCashAndCashEquivalents",  # 34%, pre-2018
        "us-gaap:EffectOfExchangeRateOnCashAndCashEquivalentsContinuingOperations",
    ),
    "capital_expenditure": (
        "us-gaap:PaymentsToAcquirePropertyPlantAndEquipment",
        "us-gaap:PaymentsToAcquireProductiveAssets",
    ),  # 91%
    # -- working capital --------------------------------------------------
    "trade_receivables": (
        "us-gaap:AccountsReceivableNetCurrent",
        "us-gaap:ReceivablesNetCurrent",
    ),  # 81%
    "trade_payables": (
        "us-gaap:AccountsPayableCurrent",
        "us-gaap:AccountsPayableTradeCurrent",
    ),  # 83%
    "inventories": ("us-gaap:InventoryNet",),  # 70%
    # -- balance sheet ----------------------------------------------------
    "total_assets": ("us-gaap:Assets",),  # 100%
    "equity_and_liabilities": ("us-gaap:LiabilitiesAndStockholdersEquity",),  # 100%
    # The same tension as net income, resolved the same way. Total equity means
    # all of it, so the including-NCI concept leads on precision; the parent-only
    # concept follows because a company without minority interest tags only that
    # and means the whole. `equity_attributable_to_owners` is left null rather
    # than sharing a tag.
    "total_equity": (
        "us-gaap:StockholdersEquityIncludingPortionAttributableToNoncontrollingInterest",
        "us-gaap:StockholdersEquity",
    ),  # 100%
    "cash_and_equivalents": (
        "us-gaap:CashAndCashEquivalentsAtCarryingValue",
        "us-gaap:CashCashEquivalentsRestrictedCashAndRestrictedCashEquivalents",
    ),  # 100%
    # 89%. A bank orders its balance sheet by liquidity and tags neither. This
    # is the single biggest difference from the Israeli market.
    "current_assets": ("us-gaap:AssetsCurrent",),  # 89%
    "current_liabilities": ("us-gaap:LiabilitiesCurrent",),  # 89%
    "property_plant_equipment": ("us-gaap:PropertyPlantAndEquipmentNet",),  # 98%
    # -- solvency ---------------------------------------------------------
    "short_term_debt": (
        "us-gaap:ShortTermBorrowings",
        "us-gaap:LongTermDebtCurrent",
        "us-gaap:OtherShortTermBorrowings",
    ),  # 77%
    "long_term_debt": (
        "us-gaap:LongTermDebtNoncurrent",
        "us-gaap:LongTermDebt",
    ),  # 91%
    # -- shareholder ------------------------------------------------------
    # Far better than the Israeli market, where share counts were tagged by
    # three and four entities. Dilution becomes a usable metric here.
    "weighted_average_shares_basic": (
        "us-gaap:WeightedAverageNumberOfSharesOutstandingBasic",
    ),  # 98%
    "weighted_average_shares_diluted": (
        "us-gaap:WeightedAverageNumberOfDilutedSharesOutstanding",
    ),  # 96%
}

# Concepts that look like a match and are not. Kept explicit so nobody adds them
# back after noticing how widely they are tagged.
DELIBERATELY_EXCLUDED: Final[dict[str, str]] = {
    "us-gaap:Liabilities": (
        "total liabilities, tagged by only 66% of the sample. Amazon, AbbVie, "
        "Coca-Cola, Eli Lilly, AT&T and Alphabet omit the subtotal entirely. "
        "Assets minus equity gives the same figure for every company, so the "
        "chain would add a null where arithmetic already has an answer"
    ),
    "us-gaap:InterestAndDividendIncomeOperating": (
        "would lift finance income coverage well above 55%, but for a bank this "
        "is operating revenue rather than a financing item. Folding it in would "
        "make a bank's net finance cost read as though its core business were a "
        "treasury position"
    ),
    "us-gaap:RevenueFromContractWithCustomerIncludingAssessedTax": (
        "kept in the chain but deliberately behind the excluding-tax concept: "
        "it bundles sales taxes collected on behalf of a government into "
        "revenue, which inflates every margin computed from it"
    ),
    "us-gaap:OperatingIncomeLossBeforeDepreciationDepletionAndAmortization": (
        "an EBITDA-like subtotal. Spec section 13 defines operating profit as "
        "reported; a chain that silently substituted a pre-depreciation figure "
        "would make margins incomparable between issuers"
    ),
}
