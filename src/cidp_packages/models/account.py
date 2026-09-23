"""Pydantic model mirroring the account_balance table (see cidp-infra Task 4)."""

from __future__ import annotations

from decimal import Decimal

from pydantic import Field

from cidp_packages.models.base import TimestampedModel


class AccountBalance(TimestampedModel):
    exchange: str
    currency: str
    total: Decimal = Field(ge=0)
    locked: Decimal = Field(ge=0)
    available: Decimal = Field(ge=0)
    source: str
