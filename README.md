# Financial Report Intelligence

Turns a long public financial report into a financial story you can check: what
happened, what is unusual, how the numbers connect, why it happened when the
company says so, and what to watch in the next report.

Every number traces back to its source filing. Calculations are deterministic;
AI is used only to find and quote textual evidence, never to compute a figure.

First market: Israel (MAGNA/XBRL). Web first, iPhone once the core is stable.

- **Specification (source of truth):** [`docs/spec.md`](docs/spec.md)
- **Working rules:** [`CLAUDE.md`](CLAUDE.md)
- **Architecture decisions:** [`docs/decisions/`](docs/decisions/)
- **Financial methodology and open questions:** [`docs/financial-methodology.md`](docs/financial-methodology.md)

## Status

**Phase 1 complete — MAGNA spike.** The provider client is read-only and
working; the exploration CLI reaches the live API. Still no financial logic and
no canonical schema: both are designed in phase 2, now informed by the real
payload rather than by assumptions (spec section 52, Task D).

What the spike measured — period shapes, restatements, concept coverage and the
size of the usable universe — is recorded in
[`docs/financial-methodology.md`](docs/financial-methodology.md).

## Layout

```
financial_core/   deterministic domain logic — no database, no HTTP, no framework
database/         SQLAlchemy models, sessions, Alembic migrations
ingestion/        provider clients, parsers, pipelines (MAGNA first)
services/api/     FastAPI service
apps/web/         Next.js app
tests/            cross-package golden and integration tests
docs/             spec, decisions, financial methodology
```

Dependencies point one way only:

```
financial_core  ->  nothing
database        ->  financial_core
ingestion       ->  financial_core, database
services/api    ->  financial_core, database, ingestion
apps/web        ->  services/api, over HTTP only
```

## Prerequisites

| Tool       | Version | Notes                                                               |
| ---------- | ------- | ------------------------------------------------------------------- |
| Python     | 3.12+   |                                                                     |
| uv         | 0.12+   | `pip install uv`                                                    |
| Node.js    | 20.9+   |                                                                     |
| PostgreSQL | 16+     | server must be reachable; only the client is needed if it is remote |
| git        | 2.28+   | required for `init.defaultBranch`                                   |

On macOS with Homebrew PostgreSQL, `psql` may not be on `PATH`. It lives in
`$(brew --prefix postgresql@16)/bin`.

## Local setup

```bash
# 1. Dependencies
make setup

# 2. Database role and databases (once)
psql -d postgres -c "CREATE ROLE fri LOGIN PASSWORD 'choose-a-password'"
psql -d postgres -c "CREATE DATABASE fri_dev OWNER fri"
psql -d postgres -c "CREATE DATABASE fri_test OWNER fri"

# 3. Configuration
cp .env.example .env                       # then set DATABASE_URL
cp apps/web/.env.example apps/web/.env.local

# 4. Migrations
make db-upgrade
```

`.env` holds credentials and is git-ignored. Never commit it.

## Running

```bash
make api    # http://127.0.0.1:8000  (docs at /docs)
make web    # http://localhost:3000
```

The home page reports whether the web app can reach the API and whether the API
can reach the database — the phase 0 exit criteria.

## Quality

```bash
make test    # full suite
make lint    # ruff, mypy, eslint, tsc, prettier
make check   # lint + test, same as CI
make format  # auto-fix
```

Tests marked `integration` need a live database and are skipped when
`DATABASE_URL` is unset.

Run `make help` for every target.

## Exploring the MAGNA provider

Read-only. Nothing writes to the database yet.

```bash
uv run --env-file .env python -m ingestion.cli entities
```

```bash
uv run --env-file .env python -m ingestion.cli concepts --contains receivable
```

```bash
uv run --env-file .env python -m ingestion.cli facts --entity 520039413 --from-year 2022 --to-year 2025
```

`--archive` writes the raw payload to `data/raw/` (git-ignored), content-addressed
so re-fetching the same payload is a no-op.
