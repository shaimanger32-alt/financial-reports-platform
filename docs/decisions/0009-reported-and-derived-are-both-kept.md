# 0009 — Reported and derived values are both kept

Status: accepted — 2026-08-09

## Context

Three questions were open after the phase 1 spike (A, F and G in
`docs/financial-methodology.md`). They are answered here because phase 2 cannot
define the canonical schema without them.

## Decision A — show what the company said and what we computed

A derived value never replaces a reported one, and a reported one never hides a
derivation. Where both exist, both are stored and both are available to the UI.

Concretely:

- `FinancialFact.origin` is `reported` or `derived`.
- A derived fact records the facts it came from, so `Q4 = FY - 9M` is auditable
  down to the two inputs.
- Q2 and Q3 are reported discretely by Israeli issuers, so for those the
  reported fact is primary and our derivation exists as a cross-check.
- Q4 is never reported, so only a derived fact exists. It is labelled as ours.
- When a reported and a derived value for the same period disagree, that is a
  data-quality event: both are kept, and the disagreement is surfaced rather
  than silently resolved.

This follows the user's instruction directly: the reader gets the company's
figure and our analysis side by side, and can tell which is which.

## Decision F — filing recency is inferred, and labelled as inferred

MAGNA supplies no publication date. Recency is therefore inferred from the
reference number (`2024-01-616266` is later than `2024-01-023212`), which held
across every sample in the spike but is an undocumented convention.

- The inference is used, and recorded as `inferred` rather than as fact.
- Anything MAGNA does not supply is reported to the user as "not provided by the
  source", never filled in with a guess.
- A future provider that supplies real publication dates replaces the inference
  without touching the financial core.

## Decision G — ordered concept fallback, with provenance

A canonical metric maps to an _ordered list_ of raw concepts, tried in order,
with an optional company-specific override. The concept actually used is stored
on every fact.

Chains are ordered by **precision first, availability second**. The concept that
means exactly what the metric means leads, even when a broader one is tagged more
widely, because a number quietly measuring something else is worse than a null.

Rejected alternative: mapping only the single standard IFRS concept. It is
simpler and perfectly honest under section 4.4, but a full sweep of all
thirty-nine entities found `ifrs-full:TradeAndOtherCurrentReceivables` reported
by eleven of them, while `ifrs-full:CurrentTradeReceivables` — the more precise
concept — is reported by thirty-one. A single-tag mapping would leave DSO, the
receivables growth gap and pattern P1 `null` for most of the market, removing
the product's core differentiation rather than protecting it.

The same sweep set the exclusions. `ifrs-full:OtherCurrentReceivables` is the
most widely tagged receivables concept of all, at thirty-six entities, and is
deliberately not in the chain: it is non-trade receivables, and including it
would inflate DSO almost everywhere.

The cost is bounded because the fallback chain is defined per metric, not per
company. Per-company overrides exist as an escape hatch for extensions, not as
the default mechanism.

## Consequences

- `FinancialFact` carries `origin`, `source_concept` and derivation lineage.
- The metric engine can ask for "the discrete quarter" and get the reported one
  when it exists, without losing the ability to show the derivation.
- Mapping tables are versioned data, not code (spec section 33).
