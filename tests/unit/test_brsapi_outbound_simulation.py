"""Simulation tests for the outbound BrsApi rate limiter.

Verifies what actually happens when a runaway consumer hits the upstream
BrsApi.ir plan. Two scenarios are modelled:

  Scenario A — "soft plan" (500 req/5min, 10,000 req/day)
    Hypothetical generous plan. Test asserts the limiter honours BOTH caps.
    500th request in 5 min must be rejected; 10,001st request on the same
    Tehran day must wait for midnight.

  Scenario B — "real plan" (1,000 req/5min, 4,000 req/day — the defaults)
    The real upstream caps. Test shows the daily cap (4,000) trips BEFORE
    the 10,000 ceiling ever matters — so a 10,000/day target is unreachable
    under the current limiter. This is the safety-margin behaviour.

Both scenarios are pure unit tests: no network, no event loop waiting —
``asyncio.sleep`` is patched so the test runs in milliseconds.
"""

from __future__ import annotations

from unittest.mock import patch

import pytest

from brsapi.rate_limiter import RateLimiter

# ── helpers ───────────────────────────────────────────────────────


def _stub_sleep(*_args, **_kwargs) -> None:  # noqa: ANN001 — patch target
    """Replace ``asyncio.sleep`` so the limiter never actually blocks."""
    return None


@pytest.fixture(autouse=True)
def _no_sleep():
    """Patch asyncio.sleep everywhere the limiter awaits it."""
    with patch("asyncio.sleep", _stub_sleep):
        yield


async def _drain(
    limiter: RateLimiter,
    n: int,
    key: str = "tsetmc",
    *,
    category_cap: int | None = None,
) -> list[Exception | None]:
    """Issue ``n`` acquire() calls; return the per-call exception (None on success).

    ``category_cap`` widens the per-category token-bucket so the GLOBAL
    limits are the only thing being tested (default bucket is 30 tokens
    with no refill, which would trip the test before the global caps do).
    """
    if category_cap is not None:
        limiter.configure(key, category_cap)
    results: list[Exception | None] = []
    for _ in range(n):
        try:
            await limiter.acquire(key)
            results.append(None)
        except Exception as exc:  # noqa: BLE001 — collect, don't rethrow
            results.append(exc)
    return results


# ── Scenario A: hypothetical generous plan ────────────────────────


async def test_scenario_a_5min_cap_500_holds() -> None:
    """500 requests inside one 5-min window must all be admitted; 501st blocked."""
    limiter = RateLimiter(daily_limit=100_000, five_min_limit=500)

    # 500 admissions are expected
    results = await _drain(limiter, 500, category_cap=1_000_000)
    assert all(r is None for r in results), "first 500 must be admitted"

    # The very next request has to either block (wait > 0) or — under
    # fail_fast — raise RateLimitExhaustedError. Confirm the limiter sees
    # the window as full.
    assert len(limiter._5min_window) == 500
    wait = limiter._wait_time_for_global_limits()
    assert wait > 0, f"5-min cap not enforced at 500 (wait={wait:.1f}s)"


async def test_scenario_a_daily_cap_10000_holds() -> None:
    """10,000 requests on one Tehran day must all be admitted; 10,001st waits for midnight."""
    # Use a huge 5-min cap so only the daily limit matters.
    limiter = RateLimiter(daily_limit=10_000, five_min_limit=100_000)

    results = await _drain(limiter, 10_000, category_cap=1_000_000)
    assert all(r is None for r in results), "first 10,000 must be admitted"
    assert limiter._daily_count == 10_000

    wait = limiter._wait_time_for_global_limits()
    # Must block (a full daily quota cannot allow an immediate request).
    assert wait > 0, f"daily cap not enforced at 10,000 (wait={wait:.1f}s)"
    # And it must be a midnight-block, not a 5-min block, so the wait is
    # at most ~24h. We allow a small slack.
    assert wait < 24 * 3600 + 60


# ── Scenario B: real plan (the safety-margin behaviour) ───────────


async def test_scenario_b_real_plan_blocks_long_before_10000() -> None:
    """The configured daily limit (4,000) trips long before any 10,000/day target.

    This is the *intended* behaviour: the limiter keeps a safety margin so
    the upstream key never gets blocked. A 10,000 req/day objective is
    therefore unreachable through the current limiter — and that is the
    point of this test (catches a regression where the cap silently
    inflates).

    To isolate the DAILY cap from the 5-min cap, the 5-min window is
    widened to 100,000 (a value no real consumer will ever hit). The
    daily cap of 4,000 must then trip on the 4,001st request.
    """
    from brsapi.rate_limiter import DEFAULT_GLOBAL_5MIN_LIMIT, DEFAULT_GLOBAL_DAILY_LIMIT

    assert DEFAULT_GLOBAL_DAILY_LIMIT == 4_000
    assert DEFAULT_GLOBAL_5MIN_LIMIT == 1_000

    limiter = RateLimiter(
        daily_limit=DEFAULT_GLOBAL_DAILY_LIMIT,  # 4,000
        five_min_limit=100_000,                  # isolate the daily cap
        fail_fast=True,                          # raise, don't sleep
    )

    # 4,000 admissions succeed under fail_fast.
    results = await _drain(limiter, 4_000, category_cap=1_000_000)
    assert all(r is None for r in results), "4,000 must be admitted"

    # 4,001st MUST raise — never reach 10,000.
    with pytest.raises(Exception) as ei:
        await limiter.acquire("tsetmc")
    assert "exhausted" in str(ei.value).lower(), str(ei.value)


async def test_scenario_b_status_snapshot_at_500_in_5min() -> None:
    """At 500/1000 in a 5-min window, the dashboard status must report 50% used."""
    limiter = RateLimiter(daily_limit=100_000, five_min_limit=1_000)
    await _drain(limiter, 500, category_cap=1_000_000)

    status = limiter.status()
    assert status["global"]["5min_count"] == 500
    assert status["global"]["5min_limit"] == 1_000
    assert status["global"]["5min_used_pct"] == 50.0
    # Daily counter untouched (we never used it).
    assert status["global"]["daily_count"] == 500


async def test_scenario_b_status_snapshot_at_4000_in_day() -> None:
    """At 4,000/4,000 in a day, dashboard must report 100% used."""
    limiter = RateLimiter(daily_limit=4_000, five_min_limit=100_000)
    await _drain(limiter, 4_000, category_cap=1_000_000)

    status = limiter.status()
    assert status["global"]["daily_count"] == 4_000
    assert status["global"]["daily_used_pct"] == 100.0
    assert status["global"]["daily_remaining"] == 0
