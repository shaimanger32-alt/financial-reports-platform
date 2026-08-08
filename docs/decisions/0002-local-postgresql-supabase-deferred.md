# 0002 — Local PostgreSQL now, Supabase deferred

Status: accepted — 2026-08-08

## Context

Spec section 9 names PostgreSQL with "Supabase at the start", including Supabase
Storage for documents. Two facts changed the timing:

- Supabase's local development flow requires Docker, which is not installed, and
  the host (macOS 13 on Intel) is outside Homebrew's supported tier.
- A PostgreSQL 16 server is already running locally.

The MVP defined in section 48 has no user accounts, so Supabase Auth is not on
the critical path, and Storage is only needed for full documents in phase 6.

## Decision

Develop against local PostgreSQL 16, reached through a single `DATABASE_URL`.
Use plain SQLAlchemy and Alembic with no Supabase-specific APIs.

This defers Supabase; it does not rule it out.

## Consequences

- No new tooling, no cost, offline and fast tests.
- Moving to Supabase later means changing a connection string, provided nothing
  outside `database/` learns about the driver.
- Storage and Auth must be revisited before phase 6.
