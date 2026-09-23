# cidp-packages

Shared, non-deployable libraries for the Crypto Investment Decision Platform
(CIDP): the typed `bitso` adapter, shared Pydantic `models` matching the DB
schema, and a `common` module (retry/backoff decorator).

Part of the CIDP polyrepo. See the umbrella repo `cidp-infra` for local
bring-up and shared CI workflows.

## Install (from a consumer repo)

No package registry for V0 — pin an exact tag directly from git (see
[`docs/adr/0001-package-distribution.md`](docs/adr/0001-package-distribution.md)):

```
cidp-packages @ git+https://github.com/fjrd12/cidp-packages@v0.1.0
```

## `bitso` — typed Bitso API v3 adapter

Async, httpx-based (see
[`docs/adr/0002-http-client.md`](docs/adr/0002-http-client.md)). Only tested
against mocked/staged HTTP responses so far — no real Bitso credentials
exist yet.

```python
from cidp_packages.bitso import BitsoClient

async with BitsoClient(api_key=..., api_secret=...) as client:
    ticker = await client.get_ticker("btc_mxn")
    order_book = await client.get_order_book("btc_mxn")
    balances = await client.get_balances()  # requires api_key/api_secret
```

Raises `BitsoAuthError`, `BitsoRateLimitError`, or `BitsoUnavailableError`
(5xx/timeout) on failure — wrap calls with `common.retry.retry_with_backoff`
rather than retrying inside the client itself.

## `models` — DB-shaped Pydantic models

Mirrors the eventual `market_price` / `market_ticker` / `market_order_book`
/ `account_balance` tables (cidp-infra Task 4). Every model requires
timezone-aware `event_timestamp` and `ingestion_timestamp` — kept distinct,
never collapsed — and rejects negative prices/amounts.

```python
from cidp_packages.models import MarketTicker

ticker = MarketTicker(
    exchange="bitso", book="btc_mxn", base_currency="btc", quote_currency="mxn",
    bid=..., ask=..., last_price=..., volume=...,
    event_timestamp=..., ingestion_timestamp=..., source="bitso_api_v3",
)
```

## `common.retry` — the ingestion retry policy

```python
from cidp_packages.common import retry_with_backoff, IngestionDegraded

@retry_with_backoff(max_attempts=3, window_seconds=600)
async def poll_ticker():
    ...
```

Max 3 attempts within a 10-minute rolling window, exponential backoff
between attempts. On exhaustion, raises `IngestionDegraded` (chained from
the last error) and logs a structured `ingestion_degraded` event — never
retries forever, never swallows the final failure. Works on sync and async
functions alike; `clock_fn`/`sleep_fn` are injectable so callers (and this
package's own tests) never need to sleep for real.

## Development

```bash
python3 -m venv .venv && .venv/bin/pip install -e ".[test]"
.venv/bin/pytest
.venv/bin/pip install ruff && .venv/bin/ruff check .
```

## Status

V0 complete (Tasks 2, 5 land here).
