# Financial methodology

This document records **how** the system computes and interprets numbers, and
**what has not been decided yet**. It is written before the code that depends on
it, so that no threshold or rule is invented silently to unblock an
implementation.

Nothing here is settled by an engineer alone. Spec section 0, rule 8 requires
thresholds to be configurable and versioned; this file is where their meaning is
justified.

Status: **phase 2 in progress.** Questions A, F and G are decided (see
[0009](decisions/0009-reported-and-derived-are-both-kept.md)) and the period
model is implemented. B to E remain open and block phases 2 to 4.
Everything under "What the phase 1 spike established" is measured, not assumed.

---

## What the phase 1 spike established

Observed directly against the MAGNA API on 2026-08-09, sample: Matrix IT
(registrar 520039413), 2022-2025, plus a coverage survey of all entities.

**Periods arrive in both cumulative and discrete form.** A single result set
contains `01/01/2023 - 30/06/2023` (year to date) _and_
`01/04/2023 - 30/06/2023` (the quarter alone). Balance sheet items arrive as a
single date. The instant/duration distinction is therefore recoverable from the
payload and does not have to be inferred.

**Only Q4 has to be derived.** Q1 is cumulative and discrete at once. Q2 and Q3
are reported discretely. Q4 never is, so `Q4 = FY - 9M` is unavoidable. The
derivation was validated against the quarters that _are_ reported:

| Year | `H1 - Q1` | reported Q2  | `9M - H1` | reported Q3  |
| ---- | --------- | ------------ | --------- | ------------ |
| 2023 | 1,286,742 | 1,286,742 ✅ | 1,333,520 | 1,333,520 ✅ |
| 2024 | 1,332,732 | 1,332,732 ✅ | 1,418,810 | 1,418,810 ✅ |

(ILS thousands, `ifrs-full:Revenue`.)

**Restatements are real and common enough to matter.** Matrix IT's total assets
were restated downward in two periods, discovered by comparing the same fact
across filings. Any pipeline that takes the first value it sees will be wrong.

**A fact repeats across filings.** Each filing carries comparatives, so one fact
appeared in up to 24 filings in the sample. Deduplication with lineage is a
correctness requirement, not an optimisation.

**Coverage of a single tag is not coverage of a metric.** The phase 1 probe used
`ifrs-full:TradeAndOtherCurrentReceivables` and found it almost empty. A full
sweep of all six receivables concepts across all thirty-nine entities, run on
2026-08-09, shows why:

| Concept                                                  | Entities | In the chain?      |
| -------------------------------------------------------- | -------- | ------------------ |
| `ifrs-full:OtherCurrentReceivables`                      | 36       | **No** — not trade |
| `ifrs-full:CurrentTradeReceivables`                      | 31       | Yes, first         |
| `ifrs-full:TradeAndOtherCurrentReceivables`              | 11       | Yes, fourth        |
| `ifrs-full:TradeReceivables`                             | 6        | Yes, second        |
| `ifrs-full:TradeAndOtherReceivables`                     | 3        | Yes, fifth         |
| `ifrs-full:CurrentReceivablesFromContractsWithCustomers` | 1        | Yes, third         |

DSO is therefore available for thirty-one entities rather than eleven — but only
because the chain leads with the _precise_ concept and excludes the most widely
tagged one. `OtherCurrentReceivables` is prepayments, tax and sundry debtors;
folding it in would inflate DSO for almost every company.

**The universe is 41 entities.** After excluding financial services, real estate,
holdings, oil and gas and biotech, roughly 20 are usable. Enough for the MVP
(5-10) and for v1 (10+), but the ceiling is low.

---

## Question A — deriving Q4, and reconciling reported against derived

**Decided — see [0009](decisions/0009-reported-and-derived-are-both-kept.md).**
Both the reported quarter and our derived one are stored, distinguished by
`origin`, with the derivation's inputs recorded. A disagreement is surfaced,
never resolved silently.

`Q4 = FY - 9M` is always needed, and every TTM aggregate, Cash Conversion, the
Accruals proxy, DSO/DIO/DPO, Interest Coverage and Asset Turnover depends on it.

Implemented in `financial_core/periods`:

- `classify` refuses to assign a quarter to a date range that does not align to
  calendar quarter boundaries. Unclassified is a usable answer; a wrong quarter
  is not.
- `derive_quarter` returns `None` when any input is missing, rather than
  treating the gap as zero.
- `derive_quarter_for_flow` raises if asked to difference a balance sheet
  instant, so the stock/flow rule cannot be forgotten at a call site.
- `reconcile` compares the issuer's quarter against ours and reports agreement
  without choosing a winner.

### Q4 is always assembled from two filings

Found while ingesting real data, and it changes how much confidence a Q4 figure
can carry.

A filing tags the periods it is about. The third-quarter report tags nine months
and the quarter; the annual report tags the year and the prior year. **No filing
carries both a full year and the preceding nine months**, so `Q4 = FY - 9M`
always draws its two inputs from two different filings.

That matters because filings do not always agree with each other. Hilan's 2022
finance costs, tagged across three of its own filings:

| Filing         | Figures                              |
| -------------- | ------------------------------------ |
| 2023-01-130443 | Q1 = 7,568,000                       |
| 2023-01-130455 | YTD-Q2 = 18,694,000, Q2 = 11,613,000 |
| 2023-01-130497 | YTD-Q3 = 20,199,000, Q3 = 6,102,000  |

The nine-month filing implies YTD-Q2 = 14,097,000, while the half-year filing
says 18,694,000. Hilan reclassified something and did not re-tag the earlier
period. Differencing across the two produces a Q3 of 1,505,000 against the
6,102,000 the issuer states — nearly four times too small.

The rule this produced:

- A derivation takes both inputs from **one filing** whenever a filing carries
  both, because a single filing is internally consistent.
- When no filing carries both, the derivation still happens and is stored as
  `usable_with_warning`. It is analysable, and it may not support a
  high-confidence finding.
- Q4 is therefore always `usable_with_warning`. That is a property of the
  source, not a defect in the calculation.

### Still open

Answered when the quality engine is built:

- Should a cross-filing derivation be suppressed entirely when the two filings
  are known to disagree elsewhere on the same concept?
- Does a derived quarter inherit the `quality_status` of its weakest input?

---

## Question B — the period entity

**Decided.** `analysis_period` is a table, referenced by foreign key from every
table that needs a period, rather than a set of columns repeated in each one.

The reason is enforcement rather than tidiness: if the period lives in one
place, the same quarter cannot be recorded as a discrete quarter in one table
and as a year-to-date window in another, which is the mixing spec section 14.6
forbids. Two check constraints mirror `FiscalPeriod.__post_init__`, so an
instant cannot carry a duration kind and a duration cannot exist without a
start — even for a row written outside the application.

---

## Open question C — Report Pulse colour rules

Spec section 6.1 defines six dimensions and three states (🟢 / 🟡 / 🔴) but no
rule that maps metrics to a state. Report Pulse is an MVP deliverable
(section 48, item 7).

Section 26.2 also shows only five dimensions, dropping Shareholder Quality.
Which is correct?

**Unresolved.**

---

## Open question D — initial threshold values

Section 17 specifies the _shape_ of a threshold but gives no values. The signal
engine cannot run without them. For example: what magnitude of DSO increase is
"material" — an absolute number of days, a relative change, or a deviation from
the company's own history?

Section 17 sets the priority order: defined magnitude first, then the company
against its own history, then consistency across periods, and peer medians only
once coverage allows.

**Unresolved.**

---

## Open question E — materiality and insight ranking

Sections 30 and 31 list the factors to weigh — materiality, magnitude versus own
history, corroborating signals, persistence, evidence strength, severity — but
not how to combine them. The score is for ordering only and is never shown as a
company grade.

**Unresolved.**

---

## Question F — restatement policy

**Decided — see [0009](decisions/0009-reported-and-derived-are-both-kept.md).**
Recency is inferred from the reference number and labelled as inferred. What
MAGNA does not supply is shown as "not provided by the source".

Raised by the phase 1 spike, which found two genuine restatements in the first
company examined:

| Concept            | Period     | Earlier filing | Later filing      |
| ------------------ | ---------- | -------------- | ----------------- |
| `ifrs-full:Assets` | 30/09/2023 | 3,928,894,000  | **3,882,556,000** |
| `ifrs-full:Assets` | 31/12/2023 | 4,084,180,000  | **4,035,232,000** |

MAGNA supplies no publication date, so recency is inferred from the reference
number (`2024-01-616266` is later than `2024-01-023212`). The ordering held
across every sample in the spike, but it is an undocumented convention and is
stored as inferred, not as fact. A provider that supplies real publication dates
replaces the inference without touching the financial core.

Both values are kept. Which one a given screen shows, and how the change is
worded, is a phase 5 presentation question — the data supports either.

---

## Question G — how deep the normalisation goes

**Decided — see [0009](decisions/0009-reported-and-derived-are-both-kept.md).**
An ordered concept fallback chain per canonical metric, with per-company
overrides as an escape hatch, and the concept actually used stored on the fact.

Spec section 12 requires mapping raw concepts to canonical metrics and allows
company-specific overrides.

Two rules order every chain:

1. **Precision before availability.** The concept that means exactly what the
   metric means comes first, even when a broader one is more widely tagged. A
   number quietly measuring something else is worse than a null.
2. **Availability breaks ties** between concepts that mean the same thing.

Mapping only the single standard concept was rejected: it is honest under
section 4.4, but it would leave DSO, the receivables growth gap and pattern P1
`null` for most of the market. The chain is defined per metric, so the cost does
not grow with each company added; per-company overrides handle extensions only.

Chains are seeded into `concept_mapping` as versioned data at `v1`, and the
concept that actually resolved is stored on every fact, so a user can always see
what a number really came from.

### Metrics that will be sparse

Measured, so nobody is surprised later:

- **Debt** is thinly tagged — `ShorttermBorrowings` 7 entities, `LongtermBorrowings` 8. Net debt, net debt to EBITDA and interest coverage will be `null` for most
  companies.
- **Share counts** are thinly tagged — 3 and 4 entities. Dilution will be `null`
  for almost everyone.

These stay `null` rather than being assembled from whatever was to hand.

---

## Recorded conventions

These follow directly from the spec and are not open:

- `null` means unknown. It is never `0`, and never an implicit positive or
  negative signal (section 4.4).
- Margin changes are reported in percentage points, not percent (section 13.2).
- Growth across zero is reported as an absolute change and a loss-to-profit
  transition, never as a percentage (section 13.1).
- Free cash flow is defined by this system as `OCF - CapEx`. It is not an IFRS
  measure and must be labelled as a system definition (section 13.3).
- Cash Conversion is only valid when TTM net income is positive and material;
  otherwise the result is `null` (section 13.3).
- Receivables and inventory pressure use a growth _gap_ in percentage points,
  not a ratio of growth rates, because the ratio is unstable near zero
  (section 13.4).
- `Funding Cost Proxy` is the permitted name for interest expense over average
  interest-bearing debt. It is not a market risk price (section 13.5).
- Quarter, YTD, TTM and annual figures are never mixed without an explicit
  normalisation step (section 14.6).
- Confidence is a product classification, not a statistical probability
  (section 20).
