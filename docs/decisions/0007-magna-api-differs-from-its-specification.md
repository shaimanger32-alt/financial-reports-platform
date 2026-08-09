# 0007 — The MAGNA API differs from its published specification

Status: accepted — 2026-08-09

## Context

`magna-xbrl-api.pdf`, dated 2023-08-07 and linked from spec section 54, documents
`POST /api/search` as synchronous, answering with:

```json
{ "status": "download", "file": "ixbrl-230618115342", "count": 2 }
```

with the result then read from `/public/search/{file}.csv|json`.

The live API observed during the phase 1 spike does not behave that way.

## Observed behaviour

```
POST /api/search              -> {"guid": "...", "status": "pending"}
GET  /public/search/{guid}.json
        403 {"message": "Missing Authentication Token"}   while generating
        200 <result rows>                                 once ready
```

- There is no `count` and no `file` field. Result size is unknown until it arrives.
- There is no status endpoint. `/api/search/{guid}`, `/api/status/{guid}` and
  `/api/result/{guid}` all return 403.
- The only way to learn that a job finished is to poll the published file.
- `GET /api/init` answers with a 302 redirect to `/public/search/init.json`.
- Generation took roughly 25 seconds for a query spanning all entities.

## Decision

Implement the observed behaviour, not the documented one:

- Poll `/public/search/{guid}.json` with a widening delay and a bounded attempt
  budget.
- Treat HTTP 403 on the result file as "not ready", never as a failure.
- Follow redirects.
- Keep every endpoint in configuration (`IngestionSettings`), so a corrected or
  versioned API can be pointed at without a code change.

## Consequences

- The published PDF cannot be trusted as a contract. Behavioural changes will be
  caught by the provider tests, which pin the flow against a stubbed transport.
- A silent revert to synchronous behaviour would break the client. The missing
  `guid` case therefore raises a clear error rather than hanging.
- Polling has a cost. Callers should ask for wide queries rather than many
  narrow ones.
