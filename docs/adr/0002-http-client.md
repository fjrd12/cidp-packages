# ADR-0002: HTTP client for the bitso adapter

**Status:** Accepted
**Date:** 2026-09-23
**Deciders:** Francisco Rodriguez

## Context

The `bitso` adapter in `cidp-packages` needs an HTTP client for ticker,
order book, and balance calls. Its two consumers: `cidp-ingestion` (a
Prefect flow polling every ~5 min — I/O-bound, benefits from async but not
required) and `cidp-api` (FastAPI, async-native; V0 doesn't call Bitso
directly from the API, but later phases' services will).

## Decision

Use **httpx**, with the adapter's public methods as `async def`.

## Options Considered

### Option A: httpx (async)
| Dimension | Assessment |
|---|---|
| Complexity | Low-Med — one extra dependency, consumers must run it in an event loop (Prefect tasks and FastAPI both support this natively) |
| Cost | None |
| Scalability | Matches the async-native FastAPI/Prefect stack already decided |
| Team familiarity | Medium |

**Pros:** No thread-pool indirection needed from FastAPI request handlers or
async Prefect tasks. One client library instead of two. `httpx` also has a
sync API if a future consumer needs it (`httpx.Client`), so this isn't a
one-way door.
**Cons:** Slightly less ubiquitous than `requests`; test mocking needs
`respx` or `httpx.MockTransport` instead of the more commonly known
`responses` library.

### Option B: requests (sync)
| Dimension | Assessment |
|---|---|
| Complexity | Low — extremely well-known |
| Cost | None |
| Scalability | Requires `run_in_executor`/`anyio.to_thread` wrapping to avoid blocking the event loop in FastAPI or async Prefect tasks |
| Team familiarity | High |

**Pros:** Simpler mental model, huge ecosystem familiarity.
**Cons:** Forces a thread-pool hop at every call site in the async parts of
the stack (`cidp-api`, async Prefect tasks) — friction that compounds as
more services consume the adapter in V1+.

## Trade-off Analysis

Given the stack is already async-first (FastAPI, Prefect), adopting `requests`
would mean wrapping every adapter call in a thread-pool indirection at each
of (eventually) several call sites, rather than paying that cost once inside
the adapter. `httpx`'s sync API is available as a fallback if a future
non-async consumer needs it, so this isn't locking anything in permanently.

## Consequences

- Easier: `cidp-api` and Prefect async tasks call the adapter directly with
  `await`, no executor wrapping.
- Harder: test mocking uses `respx`/`httpx.MockTransport` — an extra
  dependency in `cidp-packages`'s test extras, not the more familiar
  `responses`/`requests-mock`.
- Revisit: none expected; `httpx` supports both sync and async, so this
  isn't a decision that forecloses options later.

## Action Items
1. [ ] Add `httpx` as a runtime dependency, `respx` as a test dependency in `cidp-packages`.
2. [ ] `BitsoClient` methods are `async def`, usable as an async context manager.
