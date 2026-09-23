"""Exceptions raised by BitsoClient.

All map from HTTP-layer failures so callers (and the retry decorator's
`retry_on` filter) only need to reason about this small hierarchy, not
httpx's or Bitso's own error shapes.
"""

from __future__ import annotations


class BitsoAPIError(Exception):
    """Base class for any error returned by, or talking to, the Bitso API."""

    def __init__(self, message: str, status_code: int | None = None) -> None:
        self.status_code = status_code
        super().__init__(message)


class BitsoAuthError(BitsoAPIError):
    """401/403 — invalid or missing credentials."""


class BitsoRateLimitError(BitsoAPIError):
    """429 — rate limited by Bitso."""


class BitsoUnavailableError(BitsoAPIError):
    """5xx, timeout, or connection failure — treat as transient/retryable."""
