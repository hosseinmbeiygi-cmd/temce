from __future__ import annotations

import pytest

from ingestion.retry import CircuitBreaker, CircuitBreakerOpenError, retry_async


class TestRetryAsync:
    async def test_success_no_retry(self) -> None:
        call_count = 0

        async def fn() -> str:
            nonlocal call_count
            call_count += 1
            return "ok"

        result = await retry_async(fn, max_retries=3)
        assert result == "ok"
        assert call_count == 1

    async def test_retry_on_failure_then_success(self) -> None:
        call_count = 0

        async def fn() -> str:
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise TimeoutError("timeout")
            return "ok"

        result = await retry_async(fn, max_retries=3)
        assert result == "ok"
        assert call_count == 3

    async def test_exhaust_retries(self) -> None:
        call_count = 0

        async def fn() -> str:
            nonlocal call_count
            call_count += 1
            raise ConnectionError("fail")

        with pytest.raises(ConnectionError):
            await retry_async(fn, max_retries=2)
        assert call_count == 3


class TestCircuitBreaker:
    async def test_calls_succeed(self) -> None:
        cb = CircuitBreaker(failure_threshold=3, recovery_timeout=0.1)

        async def fn() -> str:
            return "ok"

        result = await cb.call(fn)
        assert result == "ok"

    async def test_opens_after_threshold(self) -> None:
        cb = CircuitBreaker(failure_threshold=2, recovery_timeout=10.0)

        async def fn() -> str:
            raise ValueError("boom")

        for _ in range(2):
            with pytest.raises(ValueError):
                await cb.call(fn)

        with pytest.raises(CircuitBreakerOpenError):
            await cb.call(fn)

    async def test_recovers_after_timeout(self) -> None:
        cb = CircuitBreaker(failure_threshold=1, recovery_timeout=0.05)

        async def fail_fn() -> str:
            raise ConnectionError("boom")

        with pytest.raises(ConnectionError):
            await cb.call(fail_fn)

        import asyncio

        await asyncio.sleep(0.06)

        async def ok_fn() -> str:
            return "recovered"

        result = await cb.call(ok_fn)
        assert result == "recovered"
