from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

import pytest
from pydantic import ValidationError

from cidp_packages.models import (
    AccountBalance,
    MarketOrderBook,
    MarketOrderBookEntry,
    MarketPrice,
    MarketTicker,
)

EVENT_TS = datetime(2026, 9, 23, 10, 0, 0, tzinfo=UTC)
INGEST_TS = datetime(2026, 9, 23, 10, 0, 3, tzinfo=UTC)


def test_market_price_keeps_event_and_ingestion_timestamps_distinct():
    price = MarketPrice(
        exchange="bitso",
        book="btc_mxn",
        base_currency="btc",
        quote_currency="mxn",
        price=Decimal("1234567.891234"),
        event_timestamp=EVENT_TS,
        ingestion_timestamp=INGEST_TS,
        source="bitso_api_v3",
    )
    assert price.event_timestamp != price.ingestion_timestamp
    assert price.event_timestamp == EVENT_TS
    assert price.ingestion_timestamp == INGEST_TS


def test_decimal_precision_preserved_from_string():
    price = MarketPrice(
        exchange="bitso",
        book="btc_mxn",
        base_currency="btc",
        quote_currency="mxn",
        price="1234567.891234567",
        event_timestamp=EVENT_TS,
        ingestion_timestamp=INGEST_TS,
        source="bitso_api_v3",
    )
    assert price.price == Decimal("1234567.891234567")


@pytest.mark.parametrize("model_cls", [MarketPrice, MarketTicker])
def test_naive_datetime_rejected(model_cls):
    kwargs = dict(
        exchange="bitso",
        book="btc_mxn",
        base_currency="btc",
        quote_currency="mxn",
        event_timestamp=datetime(2026, 9, 23, 10, 0, 0),  # naive
        ingestion_timestamp=INGEST_TS,
        source="bitso_api_v3",
    )
    if model_cls is MarketPrice:
        kwargs["price"] = Decimal(1)
    else:
        kwargs.update(bid=Decimal(1), ask=Decimal(1), last_price=Decimal(1), volume=Decimal(1))

    with pytest.raises(ValidationError):
        model_cls(**kwargs)


def test_negative_price_rejected():
    with pytest.raises(ValidationError):
        MarketPrice(
            exchange="bitso",
            book="btc_mxn",
            base_currency="btc",
            quote_currency="mxn",
            price=Decimal(-1),
            event_timestamp=EVENT_TS,
            ingestion_timestamp=INGEST_TS,
            source="bitso_api_v3",
        )


def test_order_book_allows_empty_sides():
    book = MarketOrderBook(
        exchange="bitso",
        book="btc_mxn",
        base_currency="btc",
        quote_currency="mxn",
        bids=[],
        asks=[MarketOrderBookEntry(side="ask", price=Decimal(100), amount=Decimal(1))],
        event_timestamp=EVENT_TS,
        ingestion_timestamp=INGEST_TS,
        source="bitso_api_v3",
    )
    assert book.bids == []
    assert len(book.asks) == 1


def test_order_book_rejects_mismatched_side():
    with pytest.raises(ValidationError):
        MarketOrderBook(
            exchange="bitso",
            book="btc_mxn",
            base_currency="btc",
            quote_currency="mxn",
            bids=[MarketOrderBookEntry(side="ask", price=Decimal(100), amount=Decimal(1))],
            asks=[],
            event_timestamp=EVENT_TS,
            ingestion_timestamp=INGEST_TS,
            source="bitso_api_v3",
        )


def test_account_balance_round_trip():
    balance = AccountBalance(
        exchange="bitso",
        currency="btc",
        total=Decimal("4.0"),
        locked=Decimal("0.5"),
        available=Decimal("3.5"),
        event_timestamp=EVENT_TS,
        ingestion_timestamp=INGEST_TS,
        source="bitso_api_v3",
    )
    dumped = balance.model_dump()
    restored = AccountBalance(**dumped)
    assert restored == balance
