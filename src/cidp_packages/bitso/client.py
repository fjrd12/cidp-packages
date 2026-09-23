"""Async Bitso API v3 adapter.

See ADR-0002 (docs/adr/0002-http-client.md) for why this is httpx/async.
Retries are the caller's responsibility (wrap calls with
`cidp_packages.common.retry.retry_with_backoff`) — this client raises on
the first failure of a single attempt, it does not retry internally.
"""

from __future__ import annotations

import hashlib
import hmac
import time
from types import TracebackType

import httpx

from cidp_packages.bitso.exceptions import (
    BitsoAPIError,
    BitsoAuthError,
    BitsoRateLimitError,
    BitsoUnavailableError,
)
from cidp_packages.bitso.schemas import BitsoBalance, BitsoOrderBook, BitsoTicker


class BitsoClient:
    def __init__(
        self,
        api_key: str | None = None,
        api_secret: str | None = None,
        base_url: str = "https://api.bitso.com",
        timeout: float = 10.0,
        http_client: httpx.AsyncClient | None = None,
    ) -> None:
        self._api_key = api_key
        self._api_secret = api_secret
        self._owns_client = http_client is None
        self._client = http_client or httpx.AsyncClient(base_url=base_url, timeout=timeout)

    async def __aenter__(self) -> BitsoClient:
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        if self._owns_client:
            await self._client.aclose()

    def _auth_headers(self, method: str, request_path: str, body: str = "") -> dict[str, str]:
        if not self._api_key or not self._api_secret:
            raise BitsoAuthError(
                "BitsoClient requires api_key and api_secret for authenticated endpoints"
            )
        nonce = str(int(time.time() * 1000))
        message = nonce + method.upper() + request_path + body
        signature = hmac.new(
            self._api_secret.encode("utf-8"), message.encode("utf-8"), hashlib.sha256
        ).hexdigest()
        return {"Authorization": f"Bitso {self._api_key}:{nonce}:{signature}"}

    async def _get(self, path: str, *, authenticated: bool = False) -> dict:
        headers = self._auth_headers("GET", path) if authenticated else {}
        try:
            response = await self._client.get(path, headers=headers)
        except httpx.TimeoutException as exc:
            raise BitsoUnavailableError(f"Bitso request to {path} timed out") from exc
        except httpx.HTTPError as exc:
            raise BitsoUnavailableError(f"Bitso request to {path} failed: {exc}") from exc

        if response.status_code in (401, 403):
            raise BitsoAuthError(f"Bitso auth failed for {path}", status_code=response.status_code)
        if response.status_code == 429:
            raise BitsoRateLimitError(
                f"Bitso rate limited {path}", status_code=response.status_code
            )
        if response.status_code >= 500:
            raise BitsoUnavailableError(
                f"Bitso server error on {path}", status_code=response.status_code
            )
        if response.status_code >= 400:
            raise BitsoAPIError(
                f"Bitso request to {path} failed: {response.text}", status_code=response.status_code
            )

        payload = response.json()
        if not payload.get("success", False):
            raise BitsoAPIError(f"Bitso reported failure for {path}: {payload}")
        return payload["payload"]

    async def get_ticker(self, book: str) -> BitsoTicker:
        payload = await self._get(f"/v3/ticker/?book={book}")
        return BitsoTicker.model_validate(payload)

    async def get_order_book(self, book: str, aggregate: bool = True) -> BitsoOrderBook:
        agg = "true" if aggregate else "false"
        payload = await self._get(f"/v3/order_book/?book={book}&aggregate={agg}")
        return BitsoOrderBook.model_validate(payload)

    async def get_balances(self) -> list[BitsoBalance]:
        payload = await self._get("/v3/balance/", authenticated=True)
        return [BitsoBalance.model_validate(item) for item in payload["balances"]]
