# Working rules

The full product and technical specification is `docs/spec.md`. It is the source
of truth. This file holds only the rules that repeat on every task.

## Working with Shay

- **Speak Hebrew.** Code, identifiers, file names and commit messages stay in
  English; everything said to him is Hebrew.
- **Work in stages.** Finish a layer, summarise briefly, wait for approval
  before widening scope.
- **Do the work yourself.** Only ask him to act when it needs an account, a
  permission, a secret, or something a tool genuinely cannot do.
- **Never invent a business or financial requirement.** If the spec is silent on
  a number or a rule, ask. Open questions live in
  `docs/financial-methodology.md`.
- **Before a significant architectural decision the spec has not settled:**
  present two options with their trade-offs, then a recommendation and why.
  If the spec already decided, follow it unless there is a real technical reason
  not to.
- **Financial correctness outranks delivery speed**, always.

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
8. **Build on what every issuer reports.** Per-company mapping does not scale;
   see `docs/decisions/0010`. A `CORE` metric works for every company, an
   `EXTENDED` one resolves where the data exists and is null elsewhere.

## Scope discipline

- Work the phases in `docs/spec.md` section 39. Do not start the next phase
  before the current one meets its exit criteria.
- Do not add a dependency because it might be useful later.
- Do not invent a threshold or a business rule to unblock yourself; ask.

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

- Domain codes are English (`operating_margin`); display names are localised.
- All user-facing wording lives in `apps/web/src/lib/messages.ts` and
  `explanations.ts`. The engine ships message keys and never sentences, which is
  what keeps spec section 42 enforceable.
- Currency is never hard-coded to `₪`.
- Run `make check` before committing.

## Where the project stands

Phases 0 to 3 are complete; phase 4 is partly done and phase 5 has begun.

Working end to end: MAGNA ingestion → canonical store → 35 metrics → 16 signal
rules → analysis snapshots → REST API → a Hebrew company page.

Not built yet: the pattern engine (P1–P6), watch items, Report Pulse, search,
and the evidence engine.

Still open, and blocking when reached: question C in
`docs/financial-methodology.md` — the rules that map metrics to Report Pulse
colours.

## Running it

Two servers, two terminals:

```bash
make api    # http://127.0.0.1:8000  — docs at /docs
```

```bash
make web    # http://localhost:3000
```

Loading a company from the live MAGNA API:

```bash
uv run --env-file .env python -m ingestion.cli ingest --entity 520039413 --from-year 2022 --to-year 2025
```

`make help` lists every target. Other useful CLI commands: `entities`,
`concepts --contains X`, `coverage`, `facts`, `metrics`, `signals`.

## Environment notes

- `uv` lives in `~/.local/bin`. A shell that predates that PATH entry will not
  find it.
- PostgreSQL runs locally; `psql` is not on PATH and lives under
  `$(brew --prefix postgresql@16)/bin`.
- This project has no Java, Android or mobile toolchain. `JAVA_HOME` in the
  user's shell points at Android Studio for an unrelated project and is
  irrelevant here.
