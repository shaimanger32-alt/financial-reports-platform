# 0004 — Synchronous SQLAlchemy

Status: accepted — 2026-08-08

## Context

The spec does not choose between sync and async database access. The workload is
described in sections 23 and 37: ingestion and analysis run as batch jobs, and
page views read precomputed snapshots.

## Decision

Use synchronous SQLAlchemy 2.0 with psycopg 3. FastAPI endpoints are declared
with `def`, so Starlette runs them in a threadpool.

## Consequences

- Simpler code and far simpler tests; no event-loop fixtures, no async ORM
  idioms, and the ingestion scripts are ordinary Python.
- If a future endpoint becomes I/O-bound enough to matter, it can move to async
  individually — FastAPI supports both in one app.
- Revisit if concurrency profiling shows the threadpool is the bottleneck.
