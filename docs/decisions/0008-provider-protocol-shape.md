# 0008 — Provider protocol shape

Status: accepted — 2026-08-09

## Context

Spec section 40 proposes:

```python
class FinancialDataProvider(Protocol):
    def list_entities(...): ...
    def list_filings(...): ...
    def fetch_filing_facts(...): ...
    def fetch_document(...): ...
```

The phase 1 spike showed MAGNA cannot satisfy the middle two. It has no
filing-listing endpoint, and no way to ask for the facts of one filing. It is a
fact query engine keyed by entity, concept, year and quarter. Filing identity
exists only as a `Reference Number` attached to each returned fact.

## Decision

Keep the intent of section 40 — one canonical vocabulary, swappable
implementations, no provider URL outside `ingestion/` — with a query shape a
fact-oriented source can actually serve:

```python
class FinancialDataProvider(Protocol):
    provider_code: str
    def list_entities(...) -> Sequence[ProviderEntity]: ...
    def list_concepts(...) -> Sequence[ProviderConcept]: ...
    def fetch_facts(query: FactQuery) -> FactBatch: ...
    def fetch_document(provider_filing_id: str) -> bytes: ...
```

Filings are _discovered_ from returned facts (`distinct_filings`) rather than
listed. `fetch_document` stays in the protocol and raises
`ProviderNotSupportedError` for MAGNA, so the phase 6 requirement remains visible
instead of being quietly dropped.

## Why this still works for the US

SEC EDGAR's `companyfacts` endpoint is also fact-oriented: entity in, facts out,
with an accession number on each fact. It fits `fetch_facts` directly and would
have had to be bent to fit `fetch_filing_facts`.

## Consequences

- `Filing` in phase 2 is built from discovered reference numbers, not from a
  provider-supplied list.
- MAGNA supplies no publication date, so filing recency has to be inferred.
  That inference is an open question in `docs/financial-methodology.md`.
- A provider that genuinely is filing-oriented can still implement `fetch_facts`
  by iterating its own filings internally.
