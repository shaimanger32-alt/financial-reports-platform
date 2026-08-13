# Financial methodology

This document records **how** the system computes and interprets numbers, and
**what has not been decided yet**. It is written before the code that depends on
it, so that no threshold or rule is invented silently to unblock an
implementation.

Nothing here is settled by an engineer alone. Spec section 0, rule 8 requires
thresholds to be configurable and versioned; this file is where their meaning is
justified.

Status: **phases 0 to 4 complete, phase 5 half done.** Questions A, B, D, F, G
and I are decided; C, E and H remain open. Everything under "What the phase 1
spike established" is measured, not assumed.

The product now leads with the **United States**, through SEC EDGAR. The Israeli
findings below still hold for the Israeli market and are kept: they are what
decisions 0009 and 0010 rest on, and 0011 amends 0010 for the American one.

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

**A tag's name is not its meaning.** The phase 1 probe used
`ifrs-full:TradeAndOtherCurrentReceivables` and found it almost empty. A full
sweep of all six receivables concepts across all thirty-nine entities showed
something worse than sparse coverage:

| Concept                                                  | Entities | In the chain?         |
| -------------------------------------------------------- | -------- | --------------------- |
| `ifrs-full:OtherCurrentReceivables`                      | 36       | **No** — not trade    |
| `ifrs-full:CurrentTradeReceivables`                      | 31       | Yes, first            |
| `ifrs-full:TradeAndOtherCurrentReceivables`              | 11       | **No** — see below    |
| `ifrs-full:TradeReceivables`                             | 6        | Yes, second           |
| `ifrs-full:TradeAndOtherReceivables`                     | 3        | **No** — same problem |
| `ifrs-full:CurrentReceivablesFromContractsWithCustomers` | 1        | Yes, third            |

`TradeAndOtherCurrentReceivables` says trade _and_ other, so it ought to be a
superset of trade receivables. Among the seven issuers that tag both, six use it
for the far smaller "other receivables" line instead:

| Issuer    | `CurrentTradeReceivables` | `TradeAndOtherCurrentReceivables` |
| --------- | ------------------------- | --------------------------------- |
| Matrix IT | 1,746,539,000             | 113,123,000                       |
| Hilan     | 920,000,000               | 285,000,000                       |
| C. Mer    | 188,000,000               | 28,000,000                        |
| Danel     | 304,000,000               | 23,000,000                        |
| Abra      | 186,000,000               | 18,000,000                        |

Using it as a fallback would understate DSO by an order of magnitude for any
company that tags only it. Four entities do, and all four sit outside the MVP
universe, so removing it costs nothing and prevents a badly wrong number.

**The same trap resolves the other way for payables.** Only two of the seven
issuers that tag both use `TradeAndOtherCurrentPayables` as the smaller line,
and eight issuers tag nothing else. It stays in the chain, behind the
supplier-specific concept. A DPO of a very few days is the symptom that it was
read as "other payables" for some issuer, and is worth a check in the signal
engine.

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

## Question C — Report Pulse dimensions and states

**Decided by Shay, 2026-08-12: five dimensions.** Section 6.1 lists six and
section 26.2 shows five; Shareholder Quality is dropped. The reason is coverage
rather than importance — dilution resolves for some issuers and not others, and
a band reading "not reported" at half the market teaches a reader to skip the
whole panel.

**No new threshold was invented for the states, and that was the constraint.** A
dimension's state is read off the signals that already fired in it, and those
carry severities settled in question D:

| what fired                          | state        |
| ----------------------------------- | ------------ |
| a `warning` or `critical` signal    | weak         |
| a `watch` signal                    | watch        |
| only `positive` signals             | strong       |
| nothing, and metrics resolve        | stable       |
| no metric in the dimension resolves | not reported |

An `info` signal moves nothing. A tax rate ticking up is worth saying and is not
a change in how profitable the company is.

`not reported` is a state rather than a blank, because the difference matters:
JPMorgan's working capital band reads "not reported" because a bank has no
collection days and no inventory. Reporting that as "stable" would be the
plainest possible breach of section 4.4.

So Report Pulse establishes nothing the signal engine had not. It regroups it
into the five questions a reader arrives with, and every band names the signals
it was read from so it can be checked.

---

## Question D — initial threshold values

**Decided.** Two bars, both of which a movement must clear.

**The company's own history decides whether a move is unusual.** Spec section 17
puts this second in its order of preference, and it is the part that needs no
invented number: a fifteen day move in collection says nothing at a company that
moves fifteen days every quarter, and everything at one that has never moved by
three. Median and median absolute deviation are used rather than mean and
standard deviation, because financial series are short and a single acquisition
would inflate a standard deviation enough to hide everything that followed.

Everything is measured on the **year-on-year change**, not the level. Comparing
levels across adjacent quarters mistakes seasonality for news: a retailer's
fourth quarter is meant to look unlike its third. Section 14.1 makes year on
year the default comparison anyway.

**A floor decides whether the move is worth mentioning at all.** This is the only
genuinely judgemental number, and it exists because statistical unusualness and
financial relevance are different things: a company whose collection period has
sat at exactly 50.0 days for three years moving to 50.4 is infinitely many
robust units from its norm and still a rounding artefact.

The principle behind each floor is the smallest move a careful reader would
still describe out loud — not the smallest detectable one, and not one tuned to
produce a pleasing number of signals.

| Metric                     | Floor  | Why                                                   |
| -------------------------- | ------ | ----------------------------------------------------- |
| DSO, DIO, growth gaps      | 5 days | Under a week is when invoices happen to clear         |
| Gross and operating margin | 1.0 pp | Below that, mix explains more than performance        |
| Current and quick ratio    | 0.10   | The smallest step at which the usual readings change  |
| Leverage                   | 0.25   | Same reasoning, on a measure that ranges wider        |
| Equity ratio, growth rates | 5 pp   | A twentieth of the balance sheet, or of a growth rate |
| Cash conversion            | 0.15   | 0.85 rather than 1.00 is worth saying; 0.98 is not    |
| Accruals proxy             | 2 pp   | Scaled by assets, so it moves in small numbers        |

Thresholds are versioned data at `v1`, not constants in logic (section 0,
rule 8). None is calibrated against a peer distribution: there is not yet enough
coverage to build one, which is why section 17 puts peer medians last.

### What this produces in practice

Run against the two ingested companies, sixteen quarters each:

- **Matrix IT** — one signal, margin expansion, positive.
- **Hilan** — two signals, both concerning: cash conversion fell well below its
  usual year-on-year move, and the accruals proxy rose above its own. They are
  two views of the same thing, which is what pattern P2 exists to combine.

Three signals across two companies is the intended order of magnitude. An engine
that finds thirty things wrong with every company is not being observant.

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

## Open question H — how P2 recognises an earnings-quality gap

Spec section 16 words P2 as `Net Income ↑` together with `OCF ↓/growing less`,
elevated accruals and weak cash conversion.

Taken literally, that rule does not fire on the case it was written for. Hilan's
2025-Q4 is the only earnings-quality divergence in the data: cash conversion fell
0.26 against a usual move of +0.17, and the accruals proxy rose 2.23pp against a
usual -1.62pp — sitting at -4.39 and +4.36 robust units, which is the same event
measured from two sides. Its net income fell 1.9% over the same year. Requiring
profit to have risen would leave P2 silent everywhere it can currently be
checked.

The rule as built is therefore written on the divergence rather than on the
direction of profit: **two of the three views of the gap** — cash conversion
down, accruals up, operating cash flow growth down — with profit acceleration
recorded as corroboration when present. Every input is `CORE`, so P2 works for
every issuer including banks.

**Awaiting Shay's confirmation.** The alternative is the literal reading of
section 16, which is faithful to the spec and produces nothing on any company we
hold. Reversing it is a change to `required_signals` and `minimum_required` on
one rule in `financial_core/patterns/rules.py`.

### A pattern rule carries prerequisites as well as a pool

Section 16 lists `required_signals` and `minimum_required`, which count matches
out of one pool. P1 cannot be written that way. Its wording says revenue grew,
and Electra's 2025-Q3 has both of P1's quality concerns — collection lengthened,
receivables outgrew revenue — with no revenue signal at all. Counting out of one
pool would fire P1 there and tell a reader that growth needs checking at a
company that did not grow.

`PatternRule.prerequisite_signals` is therefore a field the spec does not list:
signals that must **all** be present, because the pattern's wording rests on
them. P1 uses it for revenue; P2 does not use it at all. The pool and its
minimum are unchanged for everything else.

P1's own minimum is one concern, taken from section 16's output sentence —
"הגבייה התארכה **ו/או** המרווח נשחק" — rather than chosen. On the current data
both readings give the same result, since the only match has two concerns.

---

## Question I — terms of use for SEC EDGAR

**Decided by Shay, 2026-08-12.** Commercial and public use of the SEC EDGAR API
is cleared. Spec section 7.4 required a licensing review before a commercial
launch; for the American source that review is done and the answer is yes.

This does **not** extend to the Israeli sources. MAGNA and MAYA were never
reviewed, and the TASE data products examined on the same day price internal use
only, with distribution not offered at all — which is what a public site would
be. Publishing Israeli companies remains gated on a separate answer.

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
- **A period we do not hold is said out loud.** When a quarter's report cannot be
  retrieved, the reader is told that the report for that quarter is unavailable.
  It is never filled in, never estimated from the periods around it, and never
  skipped silently so that the gap reads as though the quarter did not exist.
  This is rule 1 — missing is unknown — carried into the presentation layer.
  There are no interior gaps in the data today; the cases that need the wording
  are the ends of a series, such as Matrix IT stopping at 2024-Q4.
- **A pattern is a combination of signals and nothing more** (section 16). It
  groups observations that are already true; it does not add a reason for them,
  and grouping never raises severity above the most severe member.
