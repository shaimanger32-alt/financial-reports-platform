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
- All user-facing wording lives in `apps/web/src/lib/i18n/{en,he}.ts`, behind
  one `Dictionary` type. The engine ships message keys and never sentences,
  which is what keeps spec section 42 enforceable as a review of two files.
- Currency is never hard-coded to `₪`.
- Run `make check` before committing.

## The market

The product is aimed at the **United States first**, through SEC EDGAR. Israel
follows once there is enough traction to ask the ISA for wider access.

The Israeli data — 8 companies, ~18,800 facts — is kept and is **not published**.
Nothing about MAGNA was deleted; both providers work. `Company.is_published`
controls what a reader sees, and it defaults to false, so loading a company and
putting it in front of someone are separate acts.

EDGAR needs no API key and no registration. It requires a `User-Agent` naming
the caller with a contact address (`SEC_EDGAR_USER_AGENT`) and fewer than ten
requests a second. That is the whole access requirement.

## Where the project stands

Phases 0 to 4 are complete. **Phase 5 is nearly done** — only watch items
(section 28) remain of its deliverables. Phase 6 has not started.

Working end to end, from the live SEC EDGAR API to stored analysis:

- **42 published US companies** (plus 4 banks held back and 8 Israeli companies
  kept unpublished), 54 in all, **3,899 snapshots** covering quarters _and_ full
  fiscal years, with roughly fifteen years of history each
- 36 metrics; 16 signal rules; **455 signals and 24 patterns** across the store
- Pattern engine (P1, P2), tiering per market, REST API serving stored snapshots
- **Accounting identities run before analysis** (section 21.2) and travel in the
  snapshot and the API. On each company's latest quarter: 133 hold, 80 are not
  checkable, **3 are broken**. They are shown to nobody: `ingestion.cli quality`
  is a development tool, because a broken identity is far more often our concept
  mapping than the issuer's arithmetic.
- **Periods are switchable**, quarters and years in separate rows and never
  mixed on one axis. Each has its own URL, which matters because most patterns
  the engine finds are not in the latest quarter.
- **Report Pulse** (section 6.1): five dimensions, each read off the signals
  that already fired in it, so it introduces no threshold of its own. A band
  that cannot be read says "not reported" rather than "stable" — JPMorgan's
  working capital, because a bank has no collection days or inventory.
- **Search** on the home page, filtering in the browser over the list already
  fetched. A deliberate call at 42 companies; it becomes a server query when the
  list is thousands, without the component changing shape.
- **Restatements are surfaced, not resolved silently** (decision 0009, section
  21.3). A calculation uses the later filing's value; the snapshot and the API
  carry both, with the filings they came from. 4,413 across 49 companies.
- **Basic validation** (section 21.1): units, values that cannot exist, and one
  filing contradicting itself. Across all 54 companies it reports exactly one
  finding — PepsiCo tags euro-denominated notes alongside dollar borrowings
  under `short_term_debt`. Deliberately narrow: a negative profit, cash flow,
  equity or working capital is real, and flagging those would bury the case
  that matters.

The web app is **bilingual**, English and Hebrew, at `/[locale]/…`. All wording
lives in `apps/web/src/lib/i18n/{en,he}.ts` behind one `Dictionary` type, so a
missing key is a type error rather than a page half in one language. Direction,
number and currency formatting follow the locale; `[locale]/layout.tsx` is the
root layout because `lang` and `dir` depend on it. Company names are never
translated and are isolated with `unicode-bidi: plaintext`, so a Latin name on a
Hebrew page keeps its own punctuation.

**Not built yet**, in the order it matters:

1. **The rest of section 21.3** — accounting standard changes, reporting
   currency changes, fiscal year-end changes, consolidated/separate mismatches.
   21.1 and 21.2 are done, and so is the restatement half of 21.3.
   Neither identities nor restatements are displayed to a reader: both reach the
   API and stop there, deliberately for identities and as an open question for
   restatements.
2. **P3-P6.** P6 is newly unblocked: `dilution_yoy` resolves for 90% of the US
   set, against three or four Israeli entities. P3 and P5 still need new signal
   rules, and those need thresholds only Shay can set.
3. **Watch items** (section 28) — the last phase 5 deliverable. A pattern
   creates one; the next quarter says whether it resolved. Needs no new
   threshold. **Sector profiles** (section 18) are blocked instead: sector is
   null for every US company, because SEC's ticker index carries none.
4. The evidence engine (phase 6) and everything downstream of it.
5. **An MCP server** (decision 0012). A read surface over stored analysis —
   snapshots, signals, patterns, identities, restatements and, once phase 6
   exists, evidence with citations. It computes nothing and states no cause the
   `explanation_status` does not support. Deliberately after phase 6: without
   evidence every answer is "cash conversion weakened, and nothing is known
   about why". It is a thin adapter over `services/api`, so waiting costs
   nothing — but **the API contract is the MCP contract**, which means no
   endpoint may start returning prose.

**Phase 6, steps 1-4 are built** and are entirely deterministic
(`financial_core/evidence/`):

- **Documents.** `SecEdgarClient.list_filings` turns a company into filing
  references with real archive URLs; `fetch_document_at` retrieves one. Verified
  against Honeywell's 10-Q: 2.75 MB of markup, 285,462 characters of text.
- **Sections and chunks**, with **character offsets that reproduce their own
  text exactly**. That invariant is what the validator rests on; without it,
  citation checking degrades to fuzzy matching. 106 sections and 127 chunks on
  the real filing, MD&A, notes and segments all recognised.
- **Retrieval** by metric vocabulary, deterministic and with no embedding model.
  It is explainable — a passage was chosen because it contains _these words_,
  which a person can check — and reproducible, which section 23 requires.
- **The citation validator.** Four ways a model fabricates, all caught against
  the real filing: words not in the document, real words at the wrong place, a
  span outside the document, and a quotation from the risk factors.
  `validate_claim` checks the model's _own prose_ for invented figures, scoped
  to **the passages it cited** — scoped to the document, "$450 million" passed,
  because those digits occur somewhere in 285,000 characters.

**Step 5 is the only one left, and the only one needing `OPENAI_API_KEY`.**

**Open decisions Shay has not made:**

- **Banks.** JPMorgan resolves 9 metrics of 35 — no current/non-current split,
  no gross profit, no revenue in the ordinary sense. All four banks are ingested
  and unpublished. Section 18 asks for a separate metric pack; nobody has
  decided whether they belong in the MVP at all.
- **The P2 rule** (question H in the methodology). It is the recommendation,
  not an approved rule.

**Settled, so nobody re-opens it:** commercial and public use of SEC EDGAR is
cleared (Shay, 2026-08-12; question I in the methodology). The Israeli sources
were not reviewed and the TASE products examined price internal use only, so
publishing Israeli companies is still gated.

## Running it

Two servers, two terminals:

```bash
make api    # http://127.0.0.1:8000  — docs at /docs
```

```bash
make web    # http://localhost:3000
```

Loading US companies from SEC EDGAR. `SEC_EDGAR_USER_AGENT` must be set:

```bash
uv run --env-file .env python -m ingestion.cli ingest-us --publish --cik 320193 789019
```

Loading a company from the live MAGNA API (Israeli, currently unpublished):

```bash
uv run --env-file .env python -m ingestion.cli ingest --entity 520039413 --from-year 2022 --to-year 2025
```

Rebuilding stored analysis after a formula, rule or tiering change, without
calling any provider:

```bash
make snapshots
```

Where the accounting identities do not close. **A development tool, not a page**
— a broken identity is far more often our concept mapping than the issuer's
arithmetic, so a reader would be told a sound filing does not add up:

```bash
uv run --env-file .env python -m ingestion.cli quality
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
