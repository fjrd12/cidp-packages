"""Shared base for models mirroring CIDP's TimescaleDB hypertables.

Every row separates `event_timestamp` (when it happened) from
`ingestion_timestamp` (when we recorded it) — never collapse the two.
"""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, field_validator


class TimestampedModel(BaseModel):
    event_timestamp: datetime
    ingestion_timestamp: datetime

    @field_validator("event_timestamp", "ingestion_timestamp")
    @classmethod
    def _require_tz_aware(cls, value: datetime) -> datetime:
        if value.tzinfo is None:
            raise ValueError("timestamp must be timezone-aware")
        return value
