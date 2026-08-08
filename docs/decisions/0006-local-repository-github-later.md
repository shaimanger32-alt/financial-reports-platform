# 0006 — Local repository now, GitHub later

Status: accepted — 2026-08-08

## Context

Phase 0 asks for basic CI. Creating a remote needs an account action that cannot
be automated here, and waiting for it would block the foundation.

## Decision

Start with a local repository on `main`. Commit a working GitHub Actions
workflow now; it stays dormant until a remote exists.

## Consequences

- No cloud backup until the remote is added. Do this at the end of phase 0.
- The workflow is untested until its first run on GitHub; it mirrors `make check`
  so local runs cover most of its surface.
