"""Unit tests for the fund-level circuit breaker (A7).

منطق گذار حالت Pure تست می‌شود؛ Backend حافظه‌ای بدون نیاز به Redis تست می‌شود.
"""

from __future__ import annotations

from services.fund_circuit_breaker import (
    FAILURE_THRESHOLD,
    OPEN_SECONDS,
    WINDOW_SECONDS,
    BreakerState,
    FundCircuitBreaker,
    decide_state,
)


def test_breaker_closed_until_threshold():
    now = 1_000.0
    state = BreakerState()
    for i in range(FAILURE_THRESHOLD - 1):
        state = decide_state(state, success=False, now=now)
        assert state.failures == i + 1
        assert state.open_until == 0.0
    state = decide_state(state, success=False, now=now)
    # گذار Pure: برچسب زمان بازشدن باید دقیقاً now+OPEN باشد (is_open وابسته به ساعت دیوار است)
    assert state.open_until == now + OPEN_SECONDS
    assert state.trips == 1


def test_breaker_success_resets_everything():
    now = 1_000.0
    state = BreakerState()
    for _ in range(FAILURE_THRESHOLD - 1):
        state = decide_state(state, success=False, now=now)
    state = decide_state(state, success=True, now=now)
    assert state.failures == 0
    assert state.open_until == 0.0


def test_breaker_window_expiry_resets_counter():
    state = BreakerState()
    state = decide_state(state, success=False, now=1_000.0)
    # خارج از پنجره → شمارش از نو
    state = decide_state(state, success=False, now=1_000.0 + WINDOW_SECONDS + 1)
    assert state.failures == 1
    assert not state.is_open


def test_breaker_open_expiry_leads_to_closed_state():
    state = BreakerState()
    for _ in range(FAILURE_THRESHOLD):
        state = decide_state(state, success=False, now=1_000.0)
    assert state.open_until == 1_000.0 + OPEN_SECONDS


async def test_breaker_memory_backend_flow():
    breaker = FundCircuitBreaker(redis_client=None)
    breaker._tried_redis = True  # اجبار به Backend حافظه‌ای
    breaker._redis = None
    fid = "tse:تست"

    assert await breaker.allow(fid) is True
    for _ in range(FAILURE_THRESHOLD):
        await breaker.record_failure(fid, "boom")
    assert await breaker.allow(fid) is False

    status = await breaker.status(fid)
    assert status["is_open"] is True
    assert status["open_seconds_left"] > 0
    assert status["last_error"] == "boom"

    open_funds = await breaker.open_funds()
    assert fid in open_funds

    await breaker.record_success(fid)
    assert await breaker.allow(fid) is True
