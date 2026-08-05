"""Unit tests for the BrsApi global quota (500 req / 5 min, 10,000 req / day).

The user's BrsApi AIO package allows at most:
  - 500 requests per sliding 5-minute window
  - 10,000 requests per calendar day (Tehran time)

``RateLimiter`` must enforce both for every request, including the ones made
through ``HistoryFetchService`` (direct ``requests`` calls).
"""

from __future__ import annotations

import pytest

from brsapi.rate_limiter import DEFAULT_GLOBAL_5MIN_LIMIT, DEFAULT_GLOBAL_DAILY_LIMIT, RateLimiter


def test_default_limits_match_quota() -> None:
    assert DEFAULT_GLOBAL_DAILY_LIMIT == 10_000
    assert DEFAULT_GLOBAL_5MIN_LIMIT == 500


async def test_five_minute_window_enforced() -> None:
    limiter = RateLimiter(daily_limit=100_000, five_min_limit=3)
    for _ in range(3):
        await limiter.acquire("tsetmc")
    wait = limiter._wait_time_for_global_limits()
    assert wait >= 290, f"5-min window not enforced (wait={wait:.1f}s)"


async def test_daily_limit_enforced() -> None:
    limiter = RateLimiter(daily_limit=2, five_min_limit=500)
    await limiter.acquire("tsetmc")
    await limiter.acquire("tsetmc")
    wait = limiter._wait_time_for_global_limits()
    # Blocks until Tehran midnight. Assert positively: a full daily quota must
    # never allow an immediate request (wait > 0). Avoid a fixed hour bound to
    # not be flaky when tests run close to midnight Tehran.
    assert wait > 0, f"daily limit not enforced (wait={wait:.1f}s)"
    assert wait < 24 * 3600 + 60, f"unexpected wait (wait={wait:.1f}s)"


async def test_daily_counter_resets_new_day() -> None:
    limiter = RateLimiter(daily_limit=10_000, five_min_limit=500)
    limiter._daily_count = 9_999
    limiter._daily_date = "1999-01-01"  # force a different date
    limiter._reset_daily_if_needed()
    assert limiter._daily_count == 0


async def test_singleton_defaults_match_config() -> None:
    from brsapi.rate_limiter import get_rate_limiter

    limiter = get_rate_limiter()
    assert limiter._daily_limit == DEFAULT_GLOBAL_DAILY_LIMIT
    assert limiter._five_min_limit == DEFAULT_GLOBAL_5MIN_LIMIT


def test_history_fetch_service_uses_rate_limiter() -> None:
    import inspect

    import brsapi.services.history_fetch_service as hfs

    src = inspect.getsource(hfs)
    assert "get_rate_limiter" in src, "HistoryFetchService bypasses the rate limiter!"
    assert "await get_rate_limiter().acquire(" in src, \
        "HistoryFetchService fetch methods must acquire() before calling the API!"


@pytest.mark.asyncio
async def test_acquire_records_every_request() -> None:
    limiter = RateLimiter(daily_limit=100, five_min_limit=100)
    await limiter.acquire("codal", endpoint="/Codal/Announcement.php")
    assert limiter._daily_count == 1
    assert limiter._endpoint_counts.get("/Codal/Announcement.php") == 1
