"""Unit tests for the core RateLimiter.

Tests match the actual RateLimiter API (token-bucket per key).
"""

from __future__ import annotations

import time


def test_rate_limiter_allows_within_limit():
    from core.rate_limit import RateLimiter

    limiter = RateLimiter()
    limiter.set_limit("test", rate=100, burst=10)
    for _ in range(10):
        assert limiter.allow("test") is True


def test_rate_limiter_blocks_excess():
    from core.rate_limit import RateLimiter

    limiter = RateLimiter()
    limiter.set_limit("test", rate=100, burst=5)
    for _ in range(5):
        limiter.allow("test")
    assert limiter.allow("test") is False


def test_rate_limiter_resets_after_window():
    from core.rate_limit import RateLimiter

    limiter = RateLimiter()
    # Window is 1 second; burst=2 means 2 tokens allowed per second
    limiter.set_limit("test", rate=100, burst=2, window_seconds=1.0)
    assert limiter.allow("test") is True
    assert limiter.allow("test") is True
    assert limiter.allow("test") is False  # Burst exhausted
    time.sleep(1.1)  # Wait for 1-second window to expire
    assert limiter.allow("test") is True  # Token should refresh


def test_different_keys_independent():
    from core.rate_limit import RateLimiter

    limiter = RateLimiter()
    limiter.set_limit("key_a", rate=100, burst=1)
    limiter.set_limit("key_b", rate=100, burst=5)
    assert limiter.allow("key_a") is True
    assert limiter.allow("key_b") is True
    assert limiter.allow("key_a") is False
    for _ in range(4):
        assert limiter.allow("key_b") is True
    assert limiter.allow("key_b") is False


def test_unlimited_key():
    from core.rate_limit import RateLimiter

    limiter = RateLimiter()
    for _ in range(1000):
        assert limiter.allow("unlimited_key") is True
