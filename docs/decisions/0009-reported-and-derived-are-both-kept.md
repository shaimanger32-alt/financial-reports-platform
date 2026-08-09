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

Rejected alternative: mapping only the single standard IFRS concept. It is
simpler and perfectly honest under section 4.4, but the spike measured that only
4 of 39 entities report `ifrs-full:TradeAndOtherCurrentReceivables`. DSO, the
receivables growth gap and pattern P1 would be `null` for almost every company,
which removes the product's core differentiation rather than protecting it.

The cost is bounded because the fallback chain is defined per metric, not per
company. Per-company overrides exist as an escape hatch for extensions, not as
the default mechanism.

## Consequences

- `FinancialFact` carries `origin`, `source_concept` and derivation lineage.
- The metric engine can ask for "the discrete quarter" and get the reported one
  when it exists, without losing the ability to show the derivation.
- Mapping tables are versioned data, not code (spec section 33).
