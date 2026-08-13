.DEFAULT_GOAL := help
SHELL := /bin/bash

UV  := uv
RUN := $(UV) run --env-file .env

.PHONY: help setup db-upgrade db-revision api web dev snapshots test test-unit lint format check clean

help: ## Show available targets
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) \
		| awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-14s\033[0m %s\n", $$1, $$2}'

# ---------------------------------------------------------------------------
# Setup
# ---------------------------------------------------------------------------
setup: ## Install Python and Node dependencies
	$(UV) sync --all-packages
	npm install

# ---------------------------------------------------------------------------
# Database
# ---------------------------------------------------------------------------
db-upgrade: ## Apply all pending migrations
	$(RUN) alembic -c database/alembic.ini upgrade head

db-revision: ## Create a migration. Usage: make db-revision m="add companies"
	$(RUN) alembic -c database/alembic.ini revision --autogenerate -m "$(m)"

# ---------------------------------------------------------------------------
# Run
# ---------------------------------------------------------------------------
api: ## Run the API at http://127.0.0.1:8000
	$(RUN) uvicorn api.main:app --reload --host 127.0.0.1 --port 8000

web: ## Run the web app at http://localhost:3000
	npm run dev

snapshots: ## Rebuild stored analysis for every company, without calling a provider
	$(RUN) python -m ingestion.cli snapshots

# ---------------------------------------------------------------------------
# Quality
# ---------------------------------------------------------------------------
test: ## Run the full test suite
	$(RUN) pytest

test-unit: ## Run tests that need no database
	$(RUN) pytest -m "not integration"

lint: ## Lint and type-check everything
	$(UV) run ruff check .
	$(UV) run ruff format --check .
	$(UV) run mypy financial_core/src database/src ingestion/src services/api/src
	npm run lint
	npm run typecheck
	npm run format:check

format: ## Auto-fix formatting
	$(UV) run ruff check --fix .
	$(UV) run ruff format .
	npm run format

check: lint test ## Everything CI runs

clean: ## Remove build and cache artefacts
	find . -type d -name __pycache__ -not -path "./node_modules/*" -exec rm -rf {} + 2>/dev/null || true
	rm -rf .pytest_cache .mypy_cache .ruff_cache apps/web/.next
