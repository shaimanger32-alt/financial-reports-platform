# 0012 — MCP is a surface over the evidence engine, not a way in

Status: accepted — 2026-08-12

## Context

Shay asked whether the Model Context Protocol fits this product. The spec does
not mention it, so the question is open, and the answer decides where it may sit
rather than whether it is allowed.

Three shapes were considered.

**As a way to reach providers.** Rejected: SEC EDGAR and MAGNA are ordinary
REST, decision 0008 already reduces every source to one provider protocol, and
MCP would be a layer between us and a payload we already parse.

**As a way to hand an LLM the raw figures and ask it to analyse them.**
Rejected, and this is the one that matters. Spec section 4.1 is explicit: AI
does not compute ratios, does not fill in missing numbers and does not decide
alone whether a company is doing well. A model given a balance sheet and asked
what happened will explain, fluently, why revenue fell — with no quote from the
filing behind it. That is section 42 broken in a single sentence, and it is the
failure this whole product is built to avoid.

**As a surface over what the deterministic engine has already produced.**
Accepted, and it fits unusually well.

## Decision

**MCP is a read surface over stored analysis, and it belongs after the evidence
engine (phase 6).**

What it may expose: snapshots, metrics, line items, signals, patterns, identity
checks and restatements — each already computed, already versioned, and each
carrying the filing it came from. Once phase 6 exists, evidence and its
citations join that list.

What it may not do: compute anything, fill a null, or state a cause the
`explanation_status` on the pattern does not already support.

The division is exactly section 4.1's. A model reading this surface is doing the
four things the spec permits — locating a relevant explanation, linking it to a
numeric signal, phrasing it accessibly, and answering questions with citations —
and none of the things it forbids.

## Why not now

- It is not in the phase list (section 39). Phase 5 is half done and phase 6 has
  not started, and `CLAUDE.md` forbids opening the next phase early.
- **Without phase 6 it sells the dull half.** Every answer would be "cash
  conversion weakened, and nothing is known about why", which is true and
  unimpressive. With evidence — "weakened, and the company writes in note 12
  that…" — it is the product.
- There are no users yet. MCP's value is distribution, and distribution is worth
  something once there is something to distribute.

## Consequences

- **The API contract is the MCP contract.** Every response already carries its
  versions, its message keys rather than sentences, and `explanation_status:
not_searched` where nobody has read the filing. Nothing has to change to keep
  the option open, and nothing may be added that would close it — in particular,
  no endpoint may start returning prose.
- When it is built it is a thin adapter over `services/api`, not a new service.
  That is a day's work, deliberately, and the reason to wait costs nothing.
- If the strategy ever changes so that MCP _is_ the product rather than a
  surface on it, that is a different decision and supersedes this one.
