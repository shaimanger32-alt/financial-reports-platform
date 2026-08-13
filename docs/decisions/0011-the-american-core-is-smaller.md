# 0011 — The American universal core is smaller than the Israeli one

Status: accepted — 2026-08-12
Amends [0010](0010-build-on-the-universal-core.md) for the `sec_edgar` provider

## Context

Decision 0010 established two tiers from a measurement: seventeen IFRS concepts
were tagged by every Israeli issuer, and thirteen metrics could be built on them
alone. Those metrics are `CORE`, and a `CORE` metric is promised to work for
every company in the market, including banks.

Pointing the product at the United States means that promise has to be re-earned
against a different taxonomy. It was measured rather than assumed.

## What was measured

Forty-seven American issuers, sampled across technology, retail, healthcare,
energy, industrials, banking, payments and telecoms, counting `us-gaap` concepts
with data since 2020.

**Nine concepts are tagged by all forty-seven**, against seventeen under IFRS:

| Statement          | Concepts                                                        |
| ------------------ | --------------------------------------------------------------- |
| Profit or loss     | net income, income tax expense                                  |
| Financial position | assets, equity, liabilities and equity, retained earnings, AOCI |
| Cash flow          | operating, investing, financing                                 |

Chains recover more than single concepts do. Revenue reaches 100% once a bank's
`RevenuesNetOfInterestExpense` is included, and profit before tax reaches 100%
across three variants. Cash and equivalents reaches 100% across two.

**The balance sheet is where the tier breaks.** IFRS requires a current and
non-current split. US GAAP does not: a bank presents an unclassified balance
sheet ordered by liquidity. JPMorgan, Morgan Stanley, Goldman Sachs and Bank of
America tag neither `AssetsCurrent` nor `LiabilitiesCurrent`, so the split
resolves for 89% of the sample and not for the market.

Two other differences are worth recording:

- **Gross profit is rarer here — 38%, against 69% under IFRS.** Amazon,
  Alphabet, Costco, AT&T and every bank present no gross profit line. Decision
  0010 already barred it from Report Pulse; the American data makes that look
  generous rather than cautious.
- **Share counts are far better tagged — 96% and 98%, against three and four
  entities in Israel.** Dilution stops being permanently null and becomes a
  usable metric, which means pattern P6 is no longer blocked on data in this
  market.

## Decision

**The tier is a property of the provider, not of the metric.** A metric is
`CORE` where its chain resolves for the whole market it is being read in, and
the same metric may be `CORE` in one market and `EXTENDED` in another.

Concretely, for `sec_edgar`:

- **Losing `CORE`:** working capital, current ratio, quick ratio. Every input is
  the current/non-current split, which 11% of the market does not present. They
  resolve where the split exists and are null elsewhere, with no special
  handling either way.
- **Keeping `CORE`:** profit and cash flow growth, effective tax rate, equity
  ratio, leverage, cash conversion, accruals, cash runway.
- **Gaining coverage:** dilution, and with it the inputs pattern P6 needs.

Leverage keeping `CORE` required a change to the formula, not just to the tier.
As first written it summed current and non-current liabilities — both universal
under IFRS, and both absent from a bank's balance sheet here — so it went null
for every American bank while both of its real inputs were present. It now takes
total liabilities from the accounting identity, `assets − equity`, which is 100%
in both markets. The tagged subtotal `us-gaap:Liabilities` remains excluded at
66%.

## Consequences

- The American floor is thinner than the Israeli one. Every company still gets
  profitability, capital structure, earnings quality and cash; liquidity is no
  longer guaranteed.
- A metric's tier is no longer a constant in the catalogue. `MarketTiering` in
  `financial_core.metrics.tiering` resolves it per market, the snapshot records
  which tiering produced it, and the API serves that as `versions.tiering`. A
  tiering may only ever be more conservative than the catalogue: promoting a
  metric to `CORE` would assert universal coverage nothing measured, and a test
  enforces it.
- The claim "a `CORE` metric works for every company" stays true, because it is
  now scoped to the market the company is in.
- `us-gaap:Liabilities` is deliberately excluded despite looking like an obvious
  match, and so is `us-gaap:InterestAndDividendIncomeOperating`, which would
  lift finance income coverage from 55% while making a bank's core business read
  as a treasury position.
