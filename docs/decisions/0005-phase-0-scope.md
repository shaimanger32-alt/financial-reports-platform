# 0005 — What phase 0 deliberately leaves out

Status: accepted — 2026-08-08

## Context

Spec section 0, rule 10 forbids features that do not yet serve the core, and
section 52 (Task D) forbids designing mappings before the real MAGNA payload has
been inspected.

## Decision

Phase 0 ships engineering foundation only:

- **No financial schema.** The Alembic history starts with an empty baseline
  revision that proves the migration path works. Company, Filing, FinancialFact
  and the rest are designed in phase 2, after the phase 1 spike.
- **No web test framework.** The web app is one health page; `tsc --noEmit`,
  `next build` and ESLint provide real validation. Vitest and testing-library
  arrive in phase 5 when there is behaviour worth asserting.
- **No CSS framework.** Styling is plain CSS modules. The design system is a
  phase 5 decision.
- **No localisation library.** The document is `lang="he" dir="rtl"`; a library
  is chosen in phase 5 when there are strings to manage.
- **No Redis, Celery, Docker or pgvector.** Added only when a measured need
  appears, per spec sections 9 and 24.

## Consequences

- Phase 0 stays reviewable, and no schema has to be unpicked when the MAGNA
  payload turns out to differ from expectations.
