# Financial methodology

This document records **how** the system computes and interprets numbers, and
**what has not been decided yet**. It is written before the code that depends on
it, so that no threshold or rule is invented silently to unblock an
implementation.

Nothing here is settled by an engineer alone. Spec section 0, rule 8 requires
thresholds to be configurable and versioned; this file is where their meaning is
justified.

Status: **empty by design.** Phase 0 ships no financial logic. The sections
below are the questions that must be answered before phases 2 to 4 can proceed.

---

## Open question A — deriving quarters from cumulative reports

**Severity: highest. Everything downstream depends on it.**

Israeli issuers report Q1, H1, 9M and a full year. Q2, Q3 and Q4 are therefore
not reported as quarters and must be derived:

```
Q2 = H1  - Q1
Q3 = 9M  - H1
Q4 = FY  - 9M
```

Almost every core metric depends on those derived figures: every TTM aggregate,
Cash Conversion, the Accruals proxy, DSO/DIO/DPO, Interest Coverage and Asset
Turnover.

Spec section 11.3 requires the derivation to be explicit and provenanced, but
does not say where the result lives. Two candidates:

1. A `FinancialFact` row flagged as derived, carrying references to the facts it
   was computed from.
2. A `CalculatedMetric`, leaving `FinancialFact` strictly as-reported.

Related sub-questions:

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
