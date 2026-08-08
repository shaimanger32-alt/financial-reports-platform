# 0001 — Repository layout

Status: accepted — 2026-08-08

## Context

The spec (section 10) asks for one monorepo with a clear separation between
domain, ingestion, API and UI, but leaves the packaging details open.

## Decision

A single repository at `~/development/financial-report-intelligence`, with four
Python packages and one Next.js app:

```
financial_core  ->  nothing
database        ->  financial_core
ingestion       ->  financial_core, database
services/api    ->  financial_core, database, ingestion
apps/web        ->  services/api, over HTTP only
```

`database/` is a package of its own rather than living inside `services/api/`,
because the ingestion pipeline needs the canonical store without depending on
the web service.

Directories for phases not yet started are not created. The spec's
`packages/design-tokens`, `packages/api-client`, `apps/mobile` and the
`financial_core` sub-packages appear when their phase begins.

## Consequences

- The one-way dependency rule is mechanically checkable and is asserted by a
  test in `financial_core/tests/test_package.py`.
- Swapping MAGNA for another provider touches `ingestion/` only.
- An extra package boundary costs a little ceremony when adding a model.
