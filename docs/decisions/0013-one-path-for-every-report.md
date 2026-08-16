# 0013 — One path for every report

Status: accepted — 2026-08-14
Amends [0010](0010-build-on-the-universal-core.md) and
[0011](0011-the-american-core-is-smaller.md) on where a decision may live

## Context

The product's promise is that a reader can check anything it says. That rests on
a quieter property nobody had written down: **every report travels the same
road**. The same checks run, in the same order, and the screen shows the result
of that one journey.

Sector and company circumstance may change _parameters_ on the road — which
threshold applies, which metrics resolve, which pack of metrics is relevant. They
may not create a second road. A company whose metric does not exist gets `null`
at the same stage every other company gets a number; it does not skip the stage.

That property had eroded. Six deviations were found by reading the code rather
than the documentation, and the first of them had already produced a wrong
number on a real company.

## The path

```
facts → validation → metrics → signals → patterns → watch items → pulse → screen
```

Every stage is a pure function of the stage before it plus versioned rules.
Nothing may skip a stage, and nothing that decides what a reader is told may
live outside one.

## What was found

**1. Validation is not on the path.** Three of its four layers are, and the
fourth is not:

| Layer                      | Where it runs                    |
| -------------------------- | -------------------------------- |
| 21.4 `QualityStatus`       | `FactSet` construction           |
| 21.2 accounting identities | `build_snapshot`                 |
| 21.3 restatements          | the snapshot pipeline            |
| **21.1 basic validation**  | **`ingestion.cli quality` only** |

Section 21.1 is a development tool that the analysis never calls. Electra
Consumer Products filed revenue scaled in thousands beside receivables scaled in
units, and the resulting DSO of 17,266 days passed through the metric engine,
raised a signal, and opened a watch item on a year-on-year move of 1,003 days —
with an empty `warnings` list at every step. Twelve readings across four
metrics. The company is Israeli and unpublished, so no reader saw it; the
mechanism that let it through is not.

`check_unit_consistency` could not have caught it. It compares the _declared_
unit — a currency code — and both figures declared the same currency. What
changed was the scale.

**2. Three notions of tier, one of them dead.** `MetricSpec.tier`,
`MarketTiering`, and a `tier` field on both `SignalRule` and `PatternRule`. The
third is documented as meaning "this rule works for every company in the
market", and **no engine reads it**. It also contradicts decision 0011 directly,
which established that a tier is a property of the provider and not a constant
on a rule.

**3. Two mechanisms for one idea.** P1 states its premise with
`prerequisite_signals`, P2 with `prerequisite_metrics`. Both mean "the wording
rests on this being true". Four more patterns are due, and each would pick one
arbitrarily.

**4. Ranking happens in the browser.** Spec section 30 asks for an insight
ranking over materiality, magnitude, corroboration, persistence and severity. It
was never built, so `CompanyReport.tsx` decides what is prominent by ad-hoc
rules. That is a business decision living in the presentation layer, where it
cannot be versioned, tested or audited.

**5. Two `QualityStatus` states are never assigned.** `REJECTED` and
`NOT_COMPARABLE` exist and are documented. Nothing sets them. `NOT_COMPARABLE`
is precisely the state the unbuilt half of section 21.3 — standard changes,
currency changes, fiscal year-end changes — was meant to produce.

**6. Watch items can only open from a pattern.** With two patterns, one of them
`EXTENDED`, a bank can never open one and a company without inventory almost
never can. The path is nominally identical for every company and produces
structurally different outcomes.

## Decision

**A stage may not exist off the path.** Concretely:

- **Basic validation moves into `build_snapshot`**, beside the identity checks,
  and its findings travel in the payload and reach the API. `ingestion.cli
quality` becomes a view over what the analysis already computed rather than a
  second implementation of it.
- **A figure that fails validation does not become a metric.** Section 21.1
  findings that indicate the figure is wrong — rather than the business being in
  trouble — mark the fact `REJECTED`, which `FactSet` already excludes. This is
  what makes non-negotiable 7 real: when correctness is uncertain, return `null`
  with a warning rather than a confident number.
- **Scale is a unit question, not a financial one.** A metric whose inputs come
  from different scales is a units defect, and detecting it needs no financial
  judgement: it is an order-of-magnitude departure from the same company's own
  history of the same figure. It therefore belongs in 21.1 and does not need a
  threshold decision from Shay, unlike anything that asserts what is
  financially normal.
- **`tier` is removed from `SignalRule` and `PatternRule`.** A rule's
  applicability follows from the metrics it watches, resolved per market by
  `MarketTiering`. A second, static answer to the same question is a
  contradiction whether or not anything reads it.
- **One premise mechanism.** `prerequisite_metrics` subsumes
  `prerequisite_signals`: a fired signal is expressible as a condition, and the
  reverse is not. P1 is expressed in the surviving mechanism before P5 and P3
  are written.
- **Ranking moves into the engine** as a stage between patterns and the screen,
  carrying a version like every other rule. The page renders the order it is
  given.

## Consequences

- Electra's readings become `null` with a stated reason, and so does every case
  of the same shape that nobody has looked for yet.
- The API grows a `validation` section. Identities, restatements and basic
  findings all reach it, which leaves one open product question — how much of
  it a reader should see — rather than four separate ones.
- Removing `tier` from two dataclasses is a breaking change to nothing, because
  nothing read it. The tests asserting it exist go with it.
- Section 30 stops being unbuilt-and-improvised and becomes unbuilt-and-absent
  until it is written, which is the honest state and the one a reader of the
  code can see.
- **Watch items opening only from patterns is left as it is**, and recorded here
  so it is a known limitation rather than an oversight. Widening them to open
  from a single severe signal would change what report memory means, and that is
  a product decision rather than a cleanup.
