# Financial methodology

This document records **how** the system computes and interprets numbers, and
**what has not been decided yet**. It is written before the code that depends on
it, so that no threshold or rule is invented silently to unblock an
implementation.

Nothing here is settled by an engineer alone. Spec section 0, rule 8 requires
thresholds to be configurable and versioned; this file is where their meaning is
justified.

Status: **no financial logic yet.** Phases 0 and 1 are complete; the sections
below are the questions that must be answered before phases 2 to 4 can proceed.
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

**Coverage of a single tag is not coverage of a metric.** Only 4 of 39 entities
report `ifrs-full:TradeAndOtherCurrentReceivables`, while the taxonomy carries at
least six receivables concepts. DSO and the receivables growth gap — the inputs
to pattern P1 — depend on resolving this.

**The universe is 41 entities.** After excluding financial services, real estate,
holdings, oil and gas and biotech, roughly 20 are usable. Enough for the MVP
(5-10) and for v1 (10+), but the ceiling is low.

---

## Open question A — deriving Q4, and reconciling reported against derived

**Severity: highest. Everything downstream depends on it.**

Reduced in scope by the spike, not eliminated. `Q4 = FY - 9M` is always needed,
and every TTM aggregate, Cash Conversion, the Accruals proxy, DSO/DIO/DPO,
Interest Coverage and Asset Turnover depends on it.

Spec section 11.3 requires the derivation to be explicit and provenanced, but
does not say where the result lives. Two candidates:

1. A `FinancialFact` row flagged as derived, carrying references to the facts it
   was computed from.
2. A `CalculatedMetric`, leaving `FinancialFact` strictly as-reported.

New sub-question raised by the spike: when a quarter is **both** reported and
derivable and the two disagree, which wins, and is the disagreement surfaced?
They matched exactly in every sample checked, which is evidence but not a
guarantee.

Remaining sub-questions:

- What happens when a required cumulative period is missing or restated?
- Balance sheet items are instants and must never be differenced this way. How
  is that enforced rather than merely documented?
- Does a derived quarter inherit the `quality_status` of its weakest input?

**Unresolved.**

---

## Open question B — the period entity

`CalculatedMetric.analysis_period_id`, `Signal.period_id`, `Pattern.period_id`
and `WatchItem.created_from_period_id` all reference an entity that spec
section 11 never defines. It needs an explicit model covering company, fiscal
year, fiscal quarter, duration kind and start/end dates.

**Unresolved.**

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

## Open question F — restatement policy

Raised by the phase 1 spike, which found two genuine restatements in the first
company examined:

| Concept            | Period     | Earlier filing | Later filing      |
| ------------------ | ---------- | -------------- | ----------------- |
| `ifrs-full:Assets` | 30/09/2023 | 3,928,894,000  | **3,882,556,000** |
| `ifrs-full:Assets` | 31/12/2023 | 4,084,180,000  | **4,035,232,000** |

Three decisions are needed:

1. Which value is presented — always the most recent, or the one as reported at
   the time of the period being viewed?
2. Is the change surfaced to the user, and if so where? Spec section 21.3
   requires a comparability warning; this is that case.
3. **MAGNA supplies no publication date.** Recency can only be inferred from the
   reference number (`2024-01-616266` later than `2024-01-023212`). The ordering
   held across every sample, but it is an undocumented convention. Is inferring
   recency from it acceptable, or must a publication date be sourced elsewhere
   before restatement logic is trusted?

**Unresolved.**

---

## Open question G — how deep the normalisation goes

Spec section 12 requires mapping raw concepts to canonical metrics and allows
company-specific overrides. The spike quantified the cost: receivables alone is
spread across at least six concepts, and only 4 of 39 entities use the one the
metric definitions would naively pick.

The trade-off:

- Map per company, and DSO, the receivables growth gap and pattern P1 work
  broadly — at the cost of manual mapping that grows with each company added.
- Map only the standard concept, and those metrics are `null` for most
  companies — honest under section 4.4, but P1 rarely fires.

**Unresolved.**

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
