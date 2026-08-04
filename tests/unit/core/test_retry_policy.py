from __future__ import annotations

import pytest


def test_retry_policy_max_retries():
    from core.retry import RetryPolicy

    policy = RetryPolicy(max_retries=3, base_delay=0.01)
    assert policy.max_retries == 3


def test_retry_policy_backoff():
    from core.retry import RetryPolicy

    policy = RetryPolicy(max_retries=3, base_delay=0.1, backoff_factor=2.0)
    delays = [policy.get_delay(attempt) for attempt in range(3)]
    assert delays[0] == pytest.approx(0.1, rel=0.5)
    assert delays[1] == pytest.approx(0.2, rel=0.5)
    assert delays[2] == pytest.approx(0.4, rel=0.5)


def test_retry_policy_jitter():
    from core.retry import RetryPolicy

    policy = RetryPolicy(max_retries=3, base_delay=0.1, jitter=0.05)
    delays = [policy.get_delay(attempt) for attempt in range(5)]
    for d in delays:
        assert d >= 0


def test_retry_decorator_success():
    from core.retry import retry

    call_count = 0

    @retry(max_retries=3, base_delay=0.01)
    async def succeeds():
        nonlocal call_count
        call_count += 1
        return "success"

    import asyncio

    result = asyncio.run(succeeds())
    assert result == "success"
    assert call_count == 1


def test_retry_decorator_failure():
    from core.retry import retry

    call_count = 0

    @retry(max_retries=2, base_delay=0.01)
    async def always_fails():
        nonlocal call_count
        call_count += 1
        raise ValueError("persistent error")

    with pytest.raises(ValueError):
        import asyncio

        asyncio.run(always_fails())
    assert call_count == 3
