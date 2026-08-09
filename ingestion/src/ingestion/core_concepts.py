"""The IFRS concepts the phase 1 coverage survey probes for.

This is a *probe list*, not the normalisation mapping. Deciding that several raw
concepts collapse into one canonical metric is spec section 12 work and lands in
phase 2, informed by what this list reveals.

The spike showed why that mapping cannot be skipped: only 4 of 39 entities report
`ifrs-full:TradeAndOtherCurrentReceivables`, while the taxonomy carries at least
five other receivables concepts. Any metric built on a single tag will be null
for most companies.
"""

from typing import Final

CORE_CONCEPTS: Final[dict[str, str]] = {
    "ifrs-full:Revenue": "Revenue",
    "ifrs-full:CostOfSales": "Cost of sales",
    "ifrs-full:GrossProfit": "Gross profit",
    "ifrs-full:ProfitLossFromOperatingActivities": "Operating profit",
    "ifrs-full:ProfitLoss": "Net profit",
    "ifrs-full:CashFlowsFromUsedInOperatingActivities": "Operating cash flow",
    "ifrs-full:PurchaseOfPropertyPlantAndEquipmentClassifiedAsInvestingActivities": "CapEx",
    "ifrs-full:Assets": "Total assets",
    "ifrs-full:CurrentAssets": "Current assets",
    "ifrs-full:CurrentLiabilities": "Current liabilities",
    "ifrs-full:CashAndCashEquivalents": "Cash",
    "ifrs-full:Inventories": "Inventories",
    "ifrs-full:TradeAndOtherCurrentReceivables": "Trade receivables",
    "ifrs-full:TradeAndOtherCurrentPayables": "Trade payables",
    "ifrs-full:FinanceCosts": "Finance costs",
}

# Alternative receivables concepts observed in the taxonomy. Recorded so the
# phase 2 mapping work starts from evidence rather than from a guess.
RECEIVABLES_CANDIDATES: Final[tuple[str, ...]] = (
    "ifrs-full:TradeAndOtherCurrentReceivables",
    "ifrs-full:CurrentTradeReceivables",
    "ifrs-full:TradeReceivables",
    "ifrs-full:TradeAndOtherReceivables",
    "ifrs-full:OtherCurrentReceivables",
    "ifrs-full:CurrentReceivablesFromContractsWithCustomers",
)
