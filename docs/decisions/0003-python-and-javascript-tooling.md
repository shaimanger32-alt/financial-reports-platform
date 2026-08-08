# 0003 — Python and JavaScript tooling

Status: accepted — 2026-08-08

## Context

Four Python packages in one repository need to import each other during
development without `sys.path` manipulation. The JavaScript side has one app and
will gain a small number of shared packages.

## Decision

**Python: `uv` workspaces.** One `.venv` at the root, every package installed
editable, one `uv.lock`. Ruff for lint and format, mypy in strict mode, pytest.

**JavaScript: npm workspaces.** npm is already present and the workspace is
small; pnpm's advantages do not yet pay for another tool.

## Consequences

- `uv sync --all-packages` is the only setup step for Python.
- uv must be installed before first setup; it is not part of a stock macOS.
- Strict mypy on financial code is deliberate: an unchecked `float | None` in a
  ratio is a correctness bug, not a style issue.
