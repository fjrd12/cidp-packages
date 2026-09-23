from __future__ import annotations

import asyncio
import logging

import pytest

from cidp_packages.common.retry import IngestionDegraded, retry_with_backoff


class FakeClock:
    """Deterministic, manually-advanced clock — never a real sleep."""

    def __init__(self) -> None:
        self.now = 0.0

    def __call__(self) -> float:
        return self.now

    def advance(self, seconds: float) -> None:
        self.now += seconds


class BoomError(Exception):
    pass


class OtherError(Exception):
    pass


def make_sync_sleep(clock: FakeClock, calls: list[float]):
    def _sleep(seconds: float) -> None:
        calls.append(seconds)
        clock.advance(seconds)

    return _sleep


def make_async_sleep(clock: FakeClock, calls: list[float]):
    async def _sleep(seconds: float) -> None:
        calls.append(seconds)
        clock.advance(seconds)

    return _sleep


# --- sync happy path ---


def test_sync_succeeds_first_try_no_sleep():
    clock = FakeClock()
    sleeps: list[float] = []
    calls = {"n": 0}

    @retry_with_backoff(clock_fn=clock, sleep_fn=make_sync_sleep(clock, sleeps))
    def flaky():
        calls["n"] += 1
        return "ok"

    assert flaky() == "ok"
    assert calls["n"] == 1
    assert sleeps == []


def test_sync_fails_once_then_succeeds():
    clock = FakeClock()
    sleeps: list[float] = []
    attempts = {"n": 0}

    @retry_with_backoff(clock_fn=clock, sleep_fn=make_sync_sleep(clock, sleeps))
    def flaky():
        attempts["n"] += 1
        if attempts["n"] < 2:
            raise BoomError("transient")
        return "ok"

    assert flaky() == "ok"
    assert attempts["n"] == 2
    assert sleeps == [1.0]  # base_delay_seconds default = 1.0


# --- exhaustion ---


def test_sync_exhausts_and_raises_ingestion_degraded():
    clock = FakeClock()
    sleeps: list[float] = []
    attempts = {"n": 0}

    @retry_with_backoff(max_attempts=3, clock_fn=clock, sleep_fn=make_sync_sleep(clock, sleeps))
    def always_fails():
        attempts["n"] += 1
        raise BoomError(f"fail {attempts['n']}")

    with pytest.raises(IngestionDegraded) as exc_info:
        always_fails()

    assert attempts["n"] == 3
    assert exc_info.value.attempts == 3
    assert isinstance(exc_info.value.last_error, BoomError)
    assert isinstance(exc_info.value.__cause__, BoomError)
    # exponential backoff: delay before attempt 2 = 1s, before attempt 3 = 2s
    assert sleeps == [1.0, 2.0]


def test_backoff_is_capped_at_max_delay():
    clock = FakeClock()
    sleeps: list[float] = []

    @retry_with_backoff(
        max_attempts=4,
        base_delay_seconds=10.0,
        max_delay_seconds=15.0,
        window_seconds=10_000,
        clock_fn=clock,
        sleep_fn=make_sync_sleep(clock, sleeps),
    )
    def always_fails():
        raise BoomError("nope")

    with pytest.raises(IngestionDegraded):
        always_fails()

    # 10, 20->capped 15, 40->capped 15
    assert sleeps == [10.0, 15.0, 15.0]


# --- retry_on filtering ---


def test_exception_not_in_retry_on_propagates_immediately():
    clock = FakeClock()
    sleeps: list[float] = []
    attempts = {"n": 0}

    @retry_with_backoff(
        retry_on=(BoomError,), clock_fn=clock, sleep_fn=make_sync_sleep(clock, sleeps)
    )
    def flaky():
        attempts["n"] += 1
        raise OtherError("not retryable")

    with pytest.raises(OtherError):
        flaky()

    assert attempts["n"] == 1
    assert sleeps == []


# --- window capping ---


def test_window_exceeded_raises_degraded_without_oversleeping():
    clock = FakeClock()
    sleeps: list[float] = []

    @retry_with_backoff(
        max_attempts=3,
        base_delay_seconds=10.0,
        max_delay_seconds=10.0,
        window_seconds=5.0,  # smaller than even the first planned delay
        clock_fn=clock,
        sleep_fn=make_sync_sleep(clock, sleeps),
    )
    def always_fails():
        raise BoomError("nope")

    with pytest.raises(IngestionDegraded) as exc_info:
        always_fails()

    assert exc_info.value.attempts == 1
    assert sleeps == []  # never slept past the window


# --- structured log + on_degraded callback ---


def test_degraded_logs_and_invokes_callback(caplog: pytest.LogCaptureFixture):
    clock = FakeClock()
    sleeps: list[float] = []
    degraded_calls: list[IngestionDegraded] = []

    @retry_with_backoff(
        max_attempts=1,
        clock_fn=clock,
        sleep_fn=make_sync_sleep(clock, sleeps),
        on_degraded=degraded_calls.append,
    )
    def always_fails():
        raise BoomError("nope")

    with caplog.at_level(logging.ERROR, logger="cidp.ingestion"):
        with pytest.raises(IngestionDegraded):
            always_fails()

    assert len(degraded_calls) == 1
    assert any(r.message == "ingestion_degraded" for r in caplog.records)


# --- async ---


@pytest.mark.asyncio
async def test_async_succeeds_first_try():
    clock = FakeClock()
    sleeps: list[float] = []

    @retry_with_backoff(clock_fn=clock, sleep_fn=make_async_sleep(clock, sleeps))
    async def flaky():
        return "ok"

    assert await flaky() == "ok"
    assert sleeps == []


@pytest.mark.asyncio
async def test_async_exhausts_and_raises_ingestion_degraded():
    clock = FakeClock()
    sleeps: list[float] = []
    attempts = {"n": 0}

    @retry_with_backoff(max_attempts=3, clock_fn=clock, sleep_fn=make_async_sleep(clock, sleeps))
    async def always_fails():
        attempts["n"] += 1
        raise BoomError("nope")

    with pytest.raises(IngestionDegraded):
        await always_fails()

    assert attempts["n"] == 3
    assert sleeps == [1.0, 2.0]


def test_decorator_preserves_async_detection():
    @retry_with_backoff()
    async def coro():
        return 1

    @retry_with_backoff()
    def plain():
        return 1

    assert asyncio.iscoroutinefunction(coro)
    assert not asyncio.iscoroutinefunction(plain)
