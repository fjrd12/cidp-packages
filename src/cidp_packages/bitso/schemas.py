"""Typed models for raw Bitso API v3 responses.

Deliberately separate from `cidp_packages.models` (the DB-shaped models):
these mirror Bitso's wire format exactly, so a Bitso API change is caught
here first rather than silently reshaping our internal schema.
"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel


class BitsoTicker(BaseModel):
    book: str
    volume: Decimal
    high: Decimal
    last: Decimal
    low: Decimal
    vwap: Decimal
    ask: Decimal
    bid: Decimal
    created_at: datetime


class BitsoOrderBookEntry(BaseModel):
    book: str
    price: Decimal
    amount: Decimal


class BitsoOrderBook(BaseModel):
    asks: list[BitsoOrderBookEntry]
    bids: list[BitsoOrderBookEntry]
    updated_at: datetime
    sequence: str


class BitsoBalance(BaseModel):
    currency: str
    total: Decimal
    locked: Decimal
    available: Decimal
