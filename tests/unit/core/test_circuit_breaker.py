from __future__ import annotations

import time

import pytest


def test_circuit_breaker_initial_state():
    from core.resilience.circuit_breaker import CircuitBreaker

    cb = CircuitBreaker(name="test", failure_threshold=3, recovery_timeout=30)
    assert cb.state == "closed"


def test_circuit_breaker_trips_on_failures():
    from core.resilience.circuit_breaker import CircuitBreaker

    cb = CircuitBreaker(name="test", failure_threshold=3, recovery_timeout=30)
    for _i in range(3):
        cb.record_failure()
    assert cb.state == "open"


def test_circuit_breaker_half_open_after_timeout():
    from core.resilience.circuit_breaker import CircuitBreaker

    cb = CircuitBreaker(name="test", failure_threshold=2, recovery_timeout=0.1)
    cb.record_failure()
    cb.record_failure()
    assert cb.state == "open"
    time.sleep(0.15)
    assert cb.state == "half_open"


def test_circuit_breaker_resets_on_success():
    from core.resilience.circuit_breaker import CircuitBreaker

    cb = CircuitBreaker(name="test", failure_threshold=3, recovery_timeout=0.1)
    cb.record_failure()
    cb.record_success()
    assert cb.state == "closed"
    assert cb.failure_count == 0


@pytest.mark.asyncio
async def test_circuit_breaker_decorator():
    from core.resilience.circuit_breaker import circuit_breaker

    call_count = 0

    @circuit_breaker(name="test_dec", failure_threshold=2, recovery_timeout=0.1)
    async def failing_func():
        nonlocal call_count
        call_count += 1
        raise ValueError("test error")

    with pytest.raises(ValueError):
        await failing_func()
