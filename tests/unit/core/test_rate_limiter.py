from __future__ import annotations

import time


def test_rate_limiter_allows_within_limit():
    from core.rate_limit import RateLimiter

    limiter = RateLimiter(max_calls=10, window_seconds=1)
    for _ in range(10):
        assert limiter.allow() is True


def test_rate_limiter_blocks_excess():
    from core.rate_limit import RateLimiter

    limiter = RateLimiter(max_calls=5, window_seconds=1)
    for _ in range(5):
        limiter.allow()
    assert limiter.allow() is False


def test_rate_limiter_resets_after_window():
    from core.rate_limit import RateLimiter

    limiter = RateLimiter(max_calls=2, window_seconds=0.1)
    assert limiter.allow() is True
    assert limiter.allow() is True
    assert limiter.allow() is False
    time.sleep(0.15)
    assert limiter.allow() is True


def test_rate_limiter_remaining():
    from core.rate_limit import RateLimiter

    limiter = RateLimiter(max_calls=10, window_seconds=60)
    for _ in range(3):
        limiter.allow()
    assert limiter.remaining() == 7


def test_rate_limiter_context_manager():
    from core.rate_limit import RateLimiter

    limiter = RateLimiter(max_calls=5, window_seconds=1)
    with limiter:
        pass
