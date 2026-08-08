# Working rules

The full product and technical specification is `docs/spec.md`. It is the source
of truth. This file holds only the rules that repeat on every task.

## Non-negotiables

1. **Missing data is `null`.** Never substitute `0` and never estimate a value
   without an explicit source.
2. **No causality without evidence.** Numbers produce signals and patterns. A
   `cause` requires an explicit quote from the filing.
3. **Deterministic first.** If it can be computed in code, it is not an AI task.
4. **Everything is traceable.** Insight → Pattern → Metric → Fact → Filing → source location.
5. **Version every analytical rule.** Formulas, mappings, signal and pattern
   rules, prompts and snapshots all carry a version.
6. **Never mix period kinds.** Quarter, YTD, TTM and annual figures are only
   combined through an explicit, provenanced derivation.
7. **When correctness is uncertain, return `null` with a warning.** Do not guess.

## Scope discipline

- Work the phases in `docs/spec.md` section 39. Do not start the next phase
  before the current one meets its exit criteria.
- Do not add a dependency because it might be useful later.
- Open financial questions are tracked in `docs/financial-methodology.md`. Do not
  invent a threshold or a business rule to unblock yourself; ask.

## Layering

Dependencies point one way only:

```
financial_core  ->  nothing
database        ->  financial_core
ingestion       ->  financial_core, database
services/api    ->  financial_core, database, ingestion
apps/web        ->  services/api, over HTTP only
```

`financial_core` must stay importable without a database or web framework, and
no provider URL may appear outside `ingestion/`.

## Conventions

- Code, identifiers, file names and commit messages in English. UI copy in Hebrew.
- Domain codes are English (`operating_margin`); display names are localised.
- Run `make check` before committing.
- Currency is never hard-coded to `₪`.

## Commands

`make help` lists everything. Most used: `make setup`, `make api`, `make web`,
`make test`, `make check`.
