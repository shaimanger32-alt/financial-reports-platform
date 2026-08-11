# 0010 — Build on the universal core, not on per-company mapping

Status: accepted — 2026-08-09
Supersedes part of [0009](0009-reported-and-derived-are-both-kept.md)

## Context

Decision 0009 permitted per-company concept overrides as an escape hatch for
issuer extensions. Hand-checking Matrix IT's DSO showed where that road leads:
`ifrs-full:TradeAndOtherCurrentReceivables` promises trade _and_ other, and six
of the seven issuers that tag it use it for the much smaller "other receivables"
line. Every such discovery is one company's quirk, learned by inspection, and
carried forever.

That does not scale. A product needing bespoke analysis per issuer cannot grow
past the companies someone has personally examined.

## What was measured

Forty-eight core statement concepts, queried across every entity that filed in 2024. Seventeen are tagged by **all** of them:

| Statement          | Concepts                                                                                                                       |
| ------------------ | ------------------------------------------------------------------------------------------------------------------------------ |
| Profit or loss     | profit, profit before tax, tax expense, finance costs, finance income, comprehensive income                                    |
| Financial position | assets, current assets, non-current assets, current liabilities, non-current liabilities, equity, equity and liabilities, cash |
| Cash flow          | operating, investing, financing                                                                                                |

Two results were not expected:

- **Revenue is tagged by 86%, not 100%.** Financial companies report interest
  and fee income instead. Every revenue-based metric is therefore conditional.
- **Gross profit is tagged by 69%.** An issuer presenting profit or loss by
  nature rather than by function has no such line to tag. It is absent, not
  untagged, and no mapping can recover it.

## Decision

**Two tiers.**

`CORE` — every input is a concept all issuers tag. A core metric works for every
company, including banks and insurers, because it describes structure rather
than operations. Thirteen metrics qualify: profit and cash flow growth,
effective tax rate, net finance cost, working capital, current ratio, quick
ratio, equity ratio, leverage, cash conversion, accruals, cash runway.

`EXTENDED` — inputs are common but not guaranteed. Resolves where the data
exists, `null` where it does not, with no special handling either way. Margins,
DSO, inventory and everything revenue-based lives here.

**Per-company overrides stop being a working practice.** The column stays in
`concept_mapping` as an emergency hatch, and we do not use it. Fallback chains
remain, because they are defined per metric rather than per company and cost
nothing to maintain — but no more concepts get added to them on a hunch.

## Consequences

- Adding a company is now free. Nothing about it has to be studied first.
- The product has a floor: every company gets thirteen metrics covering
  profitability, liquidity, capital structure, earnings quality and cash.
- Gross margin can never be a headline metric. Report Pulse cannot depend on it.
- A test asserts that every core metric still resolves when given only the
  universal line items, so the tier cannot quietly rot.
- The cash bridge identity — operating plus investing plus financing equals the
  change in cash — is now checkable for the entire market, which catches a sign
  convention read the wrong way round.
