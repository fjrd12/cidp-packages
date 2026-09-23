"""Retry/backoff decorator implementing CIDP's ingestion resilience policy.

Policy (see cidp-engineering-standards): max attempts within a rolling time
window, exponential backoff between attempts, and a hard stop — after the
last attempt fails, raise `IngestionDegraded` rather than retrying forever
or silently swallowing the failure.
"""

from __future__ import annotations

import asyncio
import functools
import inspect
import logging
import time
from collections.abc import Callable
from typing import Any, TypeVar

logger = logging.getLogger("cidp.ingestion")

F = TypeVar("F", bound=Callable[..., Any])


class IngestionDegraded(Exception):
    """Raised when a wrapped call exhausts its retry budget.

    Distinct from the underlying error so callers can catch this specifically
    to raise the `ingestion_degraded` signal, without having to enumerate
    every possible upstream exception type.
    """

    def __init__(
        self,
        func_name: str,
        attempts: int,
        window_seconds: float,
        last_error: BaseException,
    ) -> None:
        self.func_name = func_name
        self.attempts = attempts
        self.window_seconds = window_seconds
        self.last_error = last_error
        super().__init__(
            f"{func_name} degraded after {attempts} attempt(s) "
            f"within a {window_seconds:.0f}s window: {last_error!r}"
        )


def _compute_delay(attempt: int, base_delay: float, max_delay: float) -> float:
    """Delay before the given attempt (1-indexed: delay before attempt 2, 3, ...)."""
    return min(base_delay * (2 ** (attempt - 1)), max_delay)


def retry_with_backoff(
    max_attempts: int = 3,
    window_seconds: float = 600.0,
    base_delay_seconds: float = 1.0,
    max_delay_seconds: float = 60.0,
    retry_on: tuple[type[BaseException], ...] = (Exception,),
    on_degraded: Callable[[IngestionDegraded], None] | None = None,
    clock_fn: Callable[[], float] = time.monotonic,
    sleep_fn: Callable[[float], Any] | None = None,
) -> Callable[[F], F]:
    """Decorator factory implementing the CIDP Bitso-call retry policy.

    - Up to `max_attempts` total calls (1 initial + up to max_attempts-1 retries).
    - Exponential backoff between attempts: base_delay * 2**(n-1), capped at max_delay.
    - The whole sequence is bounded by `window_seconds`, measured from the first
      attempt: if the next planned delay would push the next attempt past the
      window, the decorator raises `IngestionDegraded` immediately instead of
      sleeping past the window.
    - Only exceptions matching `retry_on` are retried; anything else propagates
      immediately on the first occurrence.
    - On exhausting the retry budget, logs a structured `ingestion_degraded`
      error, invokes `on_degraded` (if given — e.g. to increment a counter),
      and raises `IngestionDegraded` chained from the last error. Never
      retries silently forever, never swallows the final failure.
    - Works on both sync and async functions; the wrapped function's
      sync/async-ness is preserved so callers (FastAPI, Prefect) detect it
      correctly.
    - `clock_fn`/`sleep_fn` are injectable so tests never sleep for real.
    """

    def decorator(func: F) -> F:
        func_name = getattr(func, "__qualname__", getattr(func, "__name__", repr(func)))
        is_async = inspect.iscoroutinefunction(func)
        sleep = sleep_fn if sleep_fn is not None else (asyncio.sleep if is_async else time.sleep)

        def _handle_exhaustion(
            start: float, attempt: int, error: BaseException
        ) -> IngestionDegraded:
            degraded = IngestionDegraded(func_name, attempt, window_seconds, error)
            logger.error(
                "ingestion_degraded",
                extra={
                    "event": "ingestion_degraded",
                    "target": func_name,
                    "attempts": attempt,
                    "window_seconds": window_seconds,
                    "error": repr(error),
                },
            )
            if on_degraded is not None:
                on_degraded(degraded)
            return degraded

        @functools.wraps(func)
        async def async_wrapper(*args: Any, **kwargs: Any) -> Any:
            start = clock_fn()
            last_error: BaseException | None = None
            for attempt in range(1, max_attempts + 1):
                try:
                    return await func(*args, **kwargs)
                except retry_on as exc:  # type: ignore[misc]
                    last_error = exc
                    if attempt >= max_attempts:
                        raise _handle_exhaustion(start, attempt, exc) from exc
                    delay = _compute_delay(attempt, base_delay_seconds, max_delay_seconds)
                    if clock_fn() - start + delay > window_seconds:
                        raise _handle_exhaustion(start, attempt, exc) from exc
                    await sleep(delay)
            # Unreachable, but keeps type-checkers happy.
            raise _handle_exhaustion(
                start, max_attempts, last_error or RuntimeError("no attempts made")
            )

        @functools.wraps(func)
        def sync_wrapper(*args: Any, **kwargs: Any) -> Any:
            start = clock_fn()
            last_error: BaseException | None = None
            for attempt in range(1, max_attempts + 1):
                try:
                    return func(*args, **kwargs)
                except retry_on as exc:  # type: ignore[misc]
                    last_error = exc
                    if attempt >= max_attempts:
                        raise _handle_exhaustion(start, attempt, exc) from exc
                    delay = _compute_delay(attempt, base_delay_seconds, max_delay_seconds)
                    if clock_fn() - start + delay > window_seconds:
                        raise _handle_exhaustion(start, attempt, exc) from exc
                    sleep(delay)
            raise _handle_exhaustion(
                start, max_attempts, last_error or RuntimeError("no attempts made")
            )

        return async_wrapper if is_async else sync_wrapper  # type: ignore[return-value]

    return decorator
