from __future__ import annotations

import httpx
import pytest
import respx
from pydantic import ValidationError

from cidp_packages.bitso.client import BitsoClient
from cidp_packages.bitso.exceptions import (
    BitsoAPIError,
    BitsoAuthError,
    BitsoRateLimitError,
    BitsoUnavailableError,
)

BASE_URL = "https://api.bitso.com"

TICKER_PAYLOAD = {
    "success": True,
    "payload": {
        "book": "btc_mxn",
        "volume": "22.31349615",
        "high": "5750.00",
        "last": "5633.98",
        "low": "5450.00",
        "vwap": "5393.15",
        "ask": "5632.24",
        "bid": "5520.01",
        "created_at": "2026-09-23T17:52:31.000+00:00",
    },
}

ORDER_BOOK_PAYLOAD = {
    "success": True,
    "payload": {
        "asks": [{"book": "btc_mxn", "price": "5632.24", "amount": "1.34491802"}],
        "bids": [{"book": "btc_mxn", "price": "5520.01", "amount": "0.5"}],
        "updated_at": "2026-09-23T17:52:31.000+00:00",
        "sequence": "27214",
    },
}

BALANCE_PAYLOAD = {
    "success": True,
    "payload": {
        "balances": [
            {"currency": "btc", "total": "4.0", "locked": "0.0", "available": "4.0"},
            {"currency": "mxn", "total": "1000.0", "locked": "0.0", "available": "1000.0"},
        ]
    },
}


@pytest.fixture
async def client():
    async with BitsoClient(api_key="key", api_secret="secret", base_url=BASE_URL) as c:
        yield c


@pytest.mark.asyncio
@respx.mock
async def test_get_ticker_happy_path(client: BitsoClient):
    respx.get(f"{BASE_URL}/v3/ticker/?book=btc_mxn").mock(
        return_value=httpx.Response(200, json=TICKER_PAYLOAD)
    )
    ticker = await client.get_ticker("btc_mxn")
    assert ticker.book == "btc_mxn"
    assert str(ticker.last) == "5633.98"


@pytest.mark.asyncio
@respx.mock
async def test_get_order_book_happy_path(client: BitsoClient):
    respx.get(f"{BASE_URL}/v3/order_book/?book=btc_mxn&aggregate=true").mock(
        return_value=httpx.Response(200, json=ORDER_BOOK_PAYLOAD)
    )
    book = await client.get_order_book("btc_mxn")
    assert len(book.asks) == 1
    assert len(book.bids) == 1
    assert book.sequence == "27214"


@pytest.mark.asyncio
@respx.mock
async def test_get_balances_happy_path_sends_auth_header(client: BitsoClient):
    route = respx.get(f"{BASE_URL}/v3/balance/").mock(
        return_value=httpx.Response(200, json=BALANCE_PAYLOAD)
    )
    balances = await client.get_balances()
    assert len(balances) == 2
    assert balances[0].currency == "btc"

    sent_request = route.calls.last.request
    auth_header = sent_request.headers["Authorization"]
    assert auth_header.startswith("Bitso key:")
    parts = auth_header.removeprefix("Bitso ").split(":")
    assert len(parts) == 3  # key, nonce, signature


@pytest.mark.asyncio
async def test_get_balances_without_credentials_raises_auth_error():
    async with BitsoClient(base_url=BASE_URL) as c:
        with pytest.raises(BitsoAuthError):
            await c.get_balances()


@pytest.mark.asyncio
@respx.mock
async def test_401_raises_bitso_auth_error(client: BitsoClient):
    respx.get(f"{BASE_URL}/v3/ticker/?book=btc_mxn").mock(return_value=httpx.Response(401))
    with pytest.raises(BitsoAuthError):
        await client.get_ticker("btc_mxn")


@pytest.mark.asyncio
@respx.mock
async def test_429_raises_bitso_rate_limit_error(client: BitsoClient):
    respx.get(f"{BASE_URL}/v3/ticker/?book=btc_mxn").mock(return_value=httpx.Response(429))
    with pytest.raises(BitsoRateLimitError):
        await client.get_ticker("btc_mxn")


@pytest.mark.asyncio
@respx.mock
async def test_500_raises_bitso_unavailable_error(client: BitsoClient):
    respx.get(f"{BASE_URL}/v3/ticker/?book=btc_mxn").mock(return_value=httpx.Response(500))
    with pytest.raises(BitsoUnavailableError):
        await client.get_ticker("btc_mxn")


@pytest.mark.asyncio
@respx.mock
async def test_timeout_raises_bitso_unavailable_error(client: BitsoClient):
    respx.get(f"{BASE_URL}/v3/ticker/?book=btc_mxn").mock(side_effect=httpx.TimeoutException("boom"))
    with pytest.raises(BitsoUnavailableError):
        await client.get_ticker("btc_mxn")


@pytest.mark.asyncio
@respx.mock
async def test_success_false_raises_bitso_api_error(client: BitsoClient):
    respx.get(f"{BASE_URL}/v3/ticker/?book=btc_mxn").mock(
        return_value=httpx.Response(200, json={"success": False, "error": {"message": "bad book"}})
    )
    with pytest.raises(BitsoAPIError):
        await client.get_ticker("btc_mxn")


@pytest.mark.asyncio
@respx.mock
async def test_malformed_payload_raises_validation_error(client: BitsoClient):
    respx.get(f"{BASE_URL}/v3/ticker/?book=btc_mxn").mock(
        return_value=httpx.Response(200, json={"success": True, "payload": {"book": "btc_mxn"}})
    )
    with pytest.raises(ValidationError):
        await client.get_ticker("btc_mxn")
