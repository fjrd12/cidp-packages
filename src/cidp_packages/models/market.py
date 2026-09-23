"""Pydantic models mirroring the market_* tables (see cidp-infra Task 4).

Every model separates `event_timestamp` (when the exchange says it happened)
from `ingestion_timestamp` (when we recorded it) — never collapse the two.
"""

from __future__ import annotations

from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, Field

from cidp_packages.models.base import TimestampedModel


class MarketPrice(TimestampedModel):
    exchange: str
    book: str
    base_currency: str
    quote_currency: str
    price: Decimal = Field(ge=0)
    source: str


class MarketTicker(TimestampedModel):
    exchange: str
    book: str
    base_currency: str
    quote_currency: str
    bid: Decimal = Field(ge=0)
    ask: Decimal = Field(ge=0)
    last_price: Decimal = Field(ge=0)
    volume: Decimal = Field(ge=0)
    source: str


class MarketOrderBookEntry(BaseModel):
    side: Literal["bid", "ask"]
    price: Decimal = Field(ge=0)
    amount: Decimal = Field(ge=0)


class MarketOrderBook(TimestampedModel):
    exchange: str
    book: str
    base_currency: str
    quote_currency: str
    bids: list[MarketOrderBookEntry]
    asks: list[MarketOrderBookEntry]
    source: str
