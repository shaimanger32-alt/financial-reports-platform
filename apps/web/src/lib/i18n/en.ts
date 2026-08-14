/**
 * English. The language the published companies file in.
 *
 * Section 42 in practice, for the strings below:
 *   permitted — the collection period lengthened
 *   forbidden — the company is pushing product onto customers
 *   permitted — inventory grew faster than sales
 *   forbidden — a write-down is coming next quarter
 *   permitted — interest cover weakened
 *   forbidden — the company is about to breach a covenant
 *
 * Nothing here states a cause. A cause needs an explicit quote from the filing,
 * which is the evidence engine's job in phase 6.
 *
 * These are written rather than translated. A sentence that reads as a
 * translation invites the reader to wonder what the original said, and the whole
 * point of this file is that the reader never has to.
 */

import type { Dictionary } from "./dictionary";

export const en: Dictionary = {
  ui: {
    tagline: "Turns a financial report into an analysis you can check.",
    strapline: "A financial report, read as a story you can verify — every figure with a source.",
    companies: "Companies",
    allCompanies: "All companies",
    noCompanies: "No companies have been loaded yet.",
    serverUnreachable: "Could not reach the server.",
    quarter: (quarter, year) => `Q${quarter} ${year}`,
    fiscalYear: (year) => `FY ${year}`,
    yearToDate: (quarter, year) => `${year} through Q${quarter}`,
    periodUnavailable: "The report for this quarter is not available",
    whatStandsOut: "What stands out",
    quarterInNumbers: "The quarter in numbers",
    yearInNumbers: "The year in numbers",
    patternBasis: "The pattern is made of these observations, and nothing else:",
    observationsOnly:
      "These are observations about numbers, and a combination of them. Why they happened is settled only when the filing itself says so.",
    signalsFooter:
      "These are observations about numbers. Why they happened is settled only when the filing itself says so.",
    trend: "Trend",
    deepDive: "All metrics",
    notComputable: "Cannot be computed",
    notReported: (inputs) => `Not reported by the company: ${inputs}`,
    singleQuarter: "a single quarter",
    yearOnYearChange: "year-on-year change",
    usualChange: "usually",
    sourceConcept: "Source",
    reported: "as reported",
    derived: "computed by us",
    language: "Language",
    reportedLines: "As reported",
    reportedLinesHint:
      "The figures exactly as the company filed them, before any calculation of ours.",
    deepDiveHint:
      "Every category opens, and each metric explains what it measures and how to read it.",
    nothingStoodOut: "No measure moved outside this company's own usual range this quarter.",
    revenueTrendTitle: "Revenue growth, year on year",
    sourceNote: "Every figure is derived from the company's own iXBRL filing.",
    coreMark: "a figure every company in this market reports",
    of: "of",
    worthWatching: "Worth a look",
    sourceInFiling: "Source in the filing",
    notEnoughHistory: "Not enough history to chart",
    searchPlaceholder: "Search by name, sector or identifier",
    searchLabel: "Search companies",
    noMatches: "No company matches that search.",
    searchCountAll: "{total} companies",
    searchCountFiltered: "{shown} of {total}",
    periods: "Periods",
    quarters: "Quarters",
    years: "Years",
    persisted: (quarters) => `held for ${quarters} quarters`,
    versions: {
      formulas: "formulas",
      rules: "rules",
      thresholds: "thresholds",
      mappings: "mappings",
      patterns: "patterns",
      tiering: "tiering",
    },
  },

  units: {
    days: (formatted) => `${formatted} days`,
    points: (formatted) => `${formatted} pp`,
  },

  pulse: {
    title: "Report pulse",
    dimensions: {
      growth: "Growth",
      profitability: "Profitability",
      earnings_quality: "Earnings quality",
      working_capital: "Working capital",
      financial_strength: "Financial strength",
    },
    states: {
      strong: "strong",
      stable: "stable",
      watch: "watch",
      weak: "weak",
      no_data: "not reported",
    },
    noDataNote:
      "The company does not report what this dimension is built from. It is not a judgement about them.",
  },

  signals: {
    "signal.liquidity_deterioration": "Liquidity weakened against this company's norm",
    "signal.leverage_increase": "Leverage rose against this company's norm",
    "signal.equity_erosion": "Equity's share of the balance sheet fell",
    "signal.earnings_cash_divergence": "Profit converted to cash less well than before",
    "signal.accruals_elevated": "The gap between accounting profit and cash widened",
    "signal.operating_cash_deterioration": "Operating cash flow weakened",
    "signal.profit_acceleration": "Net profit grew beyond its usual pace",
    "signal.tax_rate_increase": "The effective tax rate rose",
    "signal.revenue_acceleration": "Revenue grew beyond its usual pace",
    "signal.margin_expansion": "The operating margin widened",
    "signal.margin_compression": "The gross margin narrowed",
    "signal.dso_deterioration": "Collection from customers lengthened",
    "signal.inventory_build": "Inventory grew faster than sales",
    "signal.receivables_growth_gap": "Receivables grew faster than revenue",
    "signal.debt_build": "Net debt rose",
    "signal.dilution": "The diluted share count grew",
  },

  patterns: {
    "pattern.earnings_quality": {
      title: "Profit rose, cash did not keep up",
      body: "Net profit rose, but operating cash flow did not improve at the same pace, and the measures of conversion to cash weakened. This is an observation about the relationship between the two, not a claim that the profit is wrong.",
    },
    "pattern.earnings_quality.cash_declined": {
      title: "Profit rose while cash flow fell",
      body: "Net profit rose while operating cash flow fell, opening a gap between accounting profit and the cash the business generated. This is an observation about the relationship between the two, not a claim that the profit is wrong.",
    },
    "pattern.growth_quality": {
      title: "Growth arrived with questions attached",
      body: "Revenue grew beyond its usual pace, and at the same time one of the measures of growth quality weakened. This is an observation about what happened together, not a forecast about revenue ahead.",
    },
  },

  watch: {
    title: "What to check in the next report",
    intro:
      "Things an earlier report raised, and what the same measurement says now. This compares two points in time; it does not forecast.",
    openedIn: "Raised in",
    then: "Then",
    now: "Now",
    statuses: {
      "watch.opened": "Raised for watching",
      "watch.improved": "The move has narrowed",
      "watch.worsened": "The move has widened",
      "watch.resolved": "Back within the company's usual range",
      "watch.not_measurable": "Could not be measured this period",
    },
  },

  warnings: {
    missing_input: "The company did not report one of the figures",
    non_positive_base: "The comparison base is not positive, so a percentage would mislead",
    immaterial_denominator: "The denominator is too small for the ratio to mean anything",
    negative_denominator: "The denominator is negative, so the ratio would read backwards",
    derived_input: "One of the inputs was computed by us rather than reported",
    crossed_zero: "A move between loss and profit cannot be expressed as a percentage",
    single_period: "A point-in-time balance was used rather than an average",
  },

  confidence: {
    low: "a single quarter",
    medium: "held for two quarters",
    high: "supported by the filing",
  },

  patternConfidence: {
    low: "one observation carries this pattern",
    medium: "several independent measures point the same way",
    high: "supported by the filing",
  },

  severity: {
    info: "for information",
    positive: "positive",
    watch: "worth watching",
    warning: "warning",
    critical: "critical",
  },

  categories: {
    income: "Profit and loss",
    cash_flow: "Cash flow",
    working_capital: "Working capital",
    balance_sheet: "Balance sheet",
    solvency: "Financial strength",
    shareholder: "Shareholders",
  },

  categoryIntros: {
    income: "How much the company sold, how much it kept, and how that changed.",
    cash_flow: "Whether the accounting profit became actual cash.",
    working_capital: "How long money sits with customers, in inventory and with suppliers.",
    balance_sheet: "What the company holds, and how it is funded.",
    solvency: "How much the company leans on debt, and how comfortably it services it.",
    shareholder: "What is happening to the shareholder's slice.",
  },

  explanationStatus: {
    not_searched: "the filing has not been read for this yet",
    no_evidence: "no explicit explanation found in the filing",
    supported: "supported by an explanation in the filing",
    contradicted: "contradicts the explanation in the filing",
  },

  metricExplanations: {
    revenue_growth_yoy: {
      what: "How much revenue grew against the same quarter a year earlier.",
      read: "The comparison is against the matching quarter rather than the previous one, so that seasonality is removed rather than mistaken for news.",
      watch:
        "Revenue growth on its own does not say whether it arrived at a similar margin or a thinner one.",
    },
    gross_margin: {
      what: "How much of each unit of sales is left after the direct cost of what was sold.",
      read: "Driven by product mix, by pricing and by input costs.",
      watch: "Comparing companies in one industry says far more than comparing across industries.",
    },
    gross_margin_change_pp: {
      what: "The move in gross margin, in percentage points.",
      read: "From 9.1% to 10.0% is +0.9 percentage points, not +9.9%. Showing it as a percentage inflates a small move.",
    },
    operating_margin: {
      what: "Operating profit as a share of revenue, after selling and administrative costs.",
      read: "Measures how profitable the operation itself is, before financing and tax.",
    },
    operating_margin_change_pp: {
      what: "The move in operating margin, in percentage points.",
      read: "A margin widening while revenue grows points at operating leverage.",
    },
    net_margin: {
      what: "Net profit as a share of revenue, after everything.",
      read: "Also moved by financing, tax and one-off events, so it swings more than the operating margin.",
    },
    net_margin_change_pp: {
      what: "The move in net margin, in percentage points.",
      read: "A sharp move without a matching one in the operating margin usually comes from below the operating line.",
    },
    gross_profit_growth_yoy: {
      what: "Gross profit growth against the matching quarter.",
      read: "When it runs ahead of revenue growth, the margin widened.",
    },
    operating_profit_growth_yoy: {
      what: "Operating profit growth against the matching quarter.",
      read: "When the comparison base is negative or near zero, a percentage misleads and is not shown.",
    },
    net_income_growth_yoy: {
      what: "Net profit growth against the matching quarter.",
      read: "A move from loss to profit cannot be put as a percentage, and none is shown in that case.",
    },
    profit_before_tax_growth_yoy: {
      what: "Growth in profit before tax.",
      read: "Removes changes in the tax rate, so it sits closer to the operating result than net profit does.",
    },
    effective_tax_rate: {
      what: "Tax actually borne, as a share of profit before tax.",
      read: "The US federal corporate rate is 21%; Israel's is 23%. A gap usually comes from foreign operations, tax incentives or one-off differences.",
      watch: "An unusual rate in a single quarter rarely represents the rate over time.",
    },
    net_finance_cost: {
      what: "Finance costs less finance income.",
      read: "A negative figure means finance income exceeded the cost, as at a company holding large cash balances.",
    },
    cash_conversion: {
      what: "How much cash is generated per unit of profit, across four quarters.",
      read: "1.0 means accounting profit converted fully into cash. Below 1 means part of the profit has not become cash yet.",
      watch:
        "Computed only while profit is positive and material; otherwise the ratio reads as the opposite of what it means.",
    },
    accruals_proxy: {
      what: "The gap between accounting profit and actual cash flow, scaled to the size of the company.",
      read: "A high figure means profit is running ahead of cash. That can come from growth, from credit terms or from when revenue is recognised.",
      watch: "A prompt to look, and nothing more. It is never evidence of accounting manipulation.",
    },
    free_cash_flow: {
      what: "Operating cash flow less investment in property, plant and equipment.",
      read: "This is a definition of ours rather than an accounting standard. Companies define it differently from one another.",
    },
    free_cash_flow_margin: {
      what: "Free cash flow as a share of revenue.",
      read: "How much spare cash each unit of sales produced.",
    },
    operating_cash_flow_growth_yoy: {
      what: "Growth in operating cash flow against the matching quarter.",
      read: "Cash swings more than profit, because it is sensitive to when money is collected and paid.",
    },
    cash_runway_quarters: {
      what: "How many quarters the cash balance covers at the current burn.",
      read: "Computed only while operating cash flow is negative. A company generating cash has no runway to measure.",
    },
    days_sales_outstanding: {
      what: "How many days it takes on average to collect from customers.",
      read: "Built from the average receivables balance against the quarter's revenue, using the real number of days in the quarter.",
      watch:
        "A lengthening can come from credit terms, from customer mix or from timing. The filing itself is where to check.",
    },
    days_inventory_outstanding: {
      what: "How many days inventory sits before it is sold.",
      read: "Relevant to companies holding physical inventory. At a services company it is negligible or absent.",
    },
    days_payables_outstanding: {
      what: "How many days the company takes on average to pay its suppliers.",
      read: "More days means suppliers are funding more of the operation. In some business models that is bargaining power rather than distress.",
    },
    cash_conversion_cycle: {
      what: "How many days pass between paying a supplier and being paid by a customer.",
      read: "Collection days plus inventory days, less supplier credit days. A negative figure means the company collects before it pays.",
    },
    receivables_growth_gap: {
      what: "By how many percentage points receivables grew faster than revenue.",
      read: "Shown as a gap rather than a ratio, because a ratio between growth rates explodes as growth approaches zero.",
      watch: "A positive gap that persists is worth reading alongside collection days.",
    },
    inventory_growth_gap: {
      what: "By how many percentage points inventory grew faster than revenue.",
      read: "A positive gap means inventory grew faster than sales.",
      watch:
        "The system will not promise a future write-down. This is an observation, not a forecast.",
    },
    working_capital: {
      what: "Current assets less current liabilities.",
      read: "A negative figure is entirely normal in some business models — a retailer collecting in cash and paying suppliers on credit, for instance.",
    },
    current_ratio: {
      what: "Current assets against current liabilities.",
      read: "Measures the ability to cover near-term obligations. Below 1, current liabilities exceed current assets.",
      watch:
        "Not every American company splits current from non-current. A bank orders its balance sheet by liquidity, and this ratio simply does not exist for it.",
    },
    quick_ratio: {
      what: "The current ratio, without inventory.",
      read: "Inventory is the current asset hardest to turn into cash quickly, so removing it makes the test stricter.",
    },
    equity_ratio: {
      what: "How much of the balance sheet is funded by equity rather than debt.",
      read: "A higher share means less dependence on creditors.",
    },
    liabilities_to_equity: {
      what: "Total liabilities against equity.",
      read: "Measures leverage. Total liabilities is taken as assets less equity, because not every company reports it as its own line. What counts as reasonable varies enormously by industry.",
    },
    net_debt: {
      what: "Interest-bearing debt less cash.",
      read: "A negative figure means there is more cash on hand than debt.",
    },
    short_term_debt_share: {
      what: "How much of the debt falls due within a year.",
      read: "A higher share increases dependence on being able to refinance.",
    },
    interest_coverage: {
      what: "How many times operating profit covers finance costs.",
      read: "A lower figure means a larger share of operating profit goes to financing.",
      watch:
        "The system will not infer a breach of financial covenants. That needs an explicit covenant in the filing.",
    },
    asset_turnover: {
      what: "How much revenue each unit of assets generates, across four quarters.",
      read: "Measures how hard the asset base works. Services companies tend to run higher than equipment-heavy ones.",
    },
    dilution_yoy: {
      what: "How much the diluted share count grew against a year earlier.",
      read: "Growth means the same profit is divided among more shares.",
    },
  },

  lineItemExplanations: {
    revenue: {
      what: "Total sales for the quarter, as reported.",
      read: "Financial companies report interest and fee income instead of a revenue line.",
    },
    gross_profit: {
      what: "Revenue less the cost of what was sold.",
      read: "A company presenting profit or loss by nature rather than by function reports no such line at all.",
    },
    operating_profit: {
      what: "Profit from operations, before financing and tax.",
      read: "The line that describes most cleanly how the business itself is performing.",
    },
    net_income: {
      what: "Net profit, including the minority shareholders' share.",
      read: "Different from profit attributable to owners, which removes the minority's part.",
    },
    operating_cash_flow: {
      what: "Cash actually generated by ordinary operations.",
      read: "Unaffected by when revenue is recognised in the accounts, which is what makes it a check on the quality of profit.",
    },
    cash_and_equivalents: {
      what: "The cash balance at the end of the quarter.",
      read: "This is a balance at a point in time, not an amount accumulated over the quarter.",
    },
  },
};
