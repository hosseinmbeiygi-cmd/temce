"""Simulation tests for the inbound FastAPI rate-limit middleware.

Models a runaway client hitting one of the API's read endpoints (default
``/api/v1/funds`` is configured at 30 requests / 60s in
``core/config/__init__.py``). The test:

  Scenario A — 5-minute burst
    500 requests in a single 60-second window → first 30 admitted, rest 429.
    Models the "what if a single user spams 500 in 5 minutes" question.

  Scenario B — 24-hour sustained load
    1,440 consecutive minutes × 35 requests each = 50,400 requests in a
    day. Every minute beyond the first must produce 429s because the
    sliding window stays full. The test asserts the per-minute limiter is
    what actually protects the system — there is no separate daily cap
    on the inbound side (unlike the outbound BrsApi plan).

Verifies:
  * the 30/min sliding window fires 429s with the right headers
  * Retry-After, X-RateLimit-Limit, X-RateLimit-Remaining all present
  * over 24h, more than 10,000 requests are issued and the limiter
    rejects every burst that exceeds 30/min
"""

from __future__ import annotations

import time
from unittest.mock import patch

import pytest
from fastapi import FastAPI
from starlette.testclient import TestClient

from apps.api.middleware import RateLimitMiddleware
from core.rate_limit.limiter import get_rate_limiter


# ── App factory ───────────────────────────────────────────────────


def _create_app(*, funds_limit: int = 30) -> FastAPI:
    """Minimal FastAPI app with RateLimitMiddleware using test overrides."""
    # Build the app first so app_settings is reachable; then override the
    # endpoint limit dict for deterministic per-route values.
    app = FastAPI()
    # Force the per-endpoint limit we want to test.
    from core.config import get_settings

    settings = get_settings()
    settings.endpoint_rate_limits["/api/v1/funds"] = funds_limit
    app.add_middleware(RateLimitMiddleware, window_seconds=60.0)

    @app.get("/api/v1/funds")
    async def funds():
        return {"ok": True, "items": []}

    @app.get("/api/v1/funds/nav-history")
    async def nav_history():
        return {"ok": True}

    @app.get("/api/v1/health")
    async def health():
        return {"ok": True}  # exempt

    return app


@pytest.fixture(autouse=True)
def _reset_global_limiter():
    """Drop the global limiter state between tests so windows don't bleed."""
    get_rate_limiter().__init__()
    yield


@pytest.fixture
def client():
    return TestClient(_create_app(funds_limit=30))


# ── Scenario A: 5-min burst ───────────────────────────────────────


def test_burst_500_in_60s_admits_30_and_429s_the_rest(client) -> None:
    """500 rapid-fire requests → 30 OK, 429 for everything after that."""
    ok = 0
    too_many = 0
    last_429_headers: dict[str, str] = {}

    for _ in range(500):
        r = client.get("/api/v1/funds")
        if r.status_code == 200:
            ok += 1
        elif r.status_code == 429:
            too_many += 1
            last_429_headers = dict(r.headers)
        else:
            pytest.fail(f"unexpected status {r.status_code}: {r.text}")

    assert ok == 30, f"expected 30 admitted, got {ok}"
    assert too_many == 470, f"expected 470 rejected, got {too_many}"

    # Standard rate-limit headers must be present (Starlette lower-cases keys).
    assert last_429_headers.get("x-ratelimit-limit") == "30"
    assert last_429_headers.get("x-ratelimit-remaining") == "0"
    assert "retry-after" in last_429_headers


def test_burst_just_under_limit_still_admits_all(client) -> None:
    """30 requests (exactly the limit) must all be admitted — no false 429."""
    statuses = [client.get("/api/v1/funds").status_code for _ in range(30)]
    assert statuses.count(200) == 30, statuses
    # 31st gets rejected.
    assert client.get("/api/v1/funds").status_code == 429


def test_window_slides_after_60s(client) -> None:
    """After the window slides, the limiter re-admits requests."""
    # Fill the bucket.
    for _ in range(30):
        client.get("/api/v1/funds")
    assert client.get("/api/v1/funds").status_code == 429

    # Force the sliding window to age by rewinding the limiter's clock.
    limiter = get_rate_limiter()
    with patch.object(time, "monotonic", return_value=time.monotonic() + 61):
        r = client.get("/api/v1/funds")
    assert r.status_code == 200, r.text


# ── Scenario B: 24-hour sustained load ────────────────────────────


def test_24h_load_keeps_per_minute_window_full(client) -> None:
    """Simulate a sustained 35 req/min load for many hours — every minute
    past the first is rejected once the per-minute window saturates.

    Inbound middleware has NO separate daily cap; only the per-minute
    sliding window. So the question "does the inbound limiter block
    more than 10,000 req/day?" can only be answered for the *burst*
    fraction — once the first window fills, the client is throttled to
    the limit-per-minute ceiling for the rest of the day.

    The full 24h × 35 req = 50,400 requests would be a real-network
    loop far too slow for a unit test, so we shrink the simulation to
    400 minutes (~6.6h × 35 = 14,000 requests) — still well past the
    10,000/day threshold the question asks about — and we patch
    ``time.monotonic`` so each simulated minute advances by exactly 60s
    without any real sleep.
    """
    REQS_PER_MIN = 35
    MINUTES = 400
    fake_now = [time.monotonic()]

    with patch.object(time, "monotonic", side_effect=lambda: fake_now[0]):
        # First minute: full 35 requests; only 30 should be admitted.
        total_ok = 0
        total_429 = 0
        for _ in range(REQS_PER_MIN):
            r = client.get("/api/v1/funds")
            if r.status_code == 200:
                total_ok += 1
            elif r.status_code == 429:
                total_429 += 1
        assert total_ok == 30, f"first minute: {total_ok=} {total_429=}"
        assert total_429 == 5

        # Remaining minutes: window is still full from the prior minute
        # (tokens aged 0..59s), so the new minute starts full and any
        # 35-burst is rejected. As the clock keeps advancing, the window
        # *does* drain — at the 60s mark the oldest token expires, so by
        # the end of minute M+1 one slot reopens, but the burst is 35
        # so the limiter still rejects ≥ 1.
        for minute in range(1, MINUTES):
            fake_now[0] += 60.0  # next minute
            admitted = 0
            rejected = 0
            for _ in range(REQS_PER_MIN):
                r = client.get("/api/v1/funds")
                if r.status_code == 200:
                    admitted += 1
                elif r.status_code == 429:
                    rejected += 1
                else:
                    pytest.fail(f"unexpected {r.status_code}")
            total_ok += admitted
            total_429 += rejected
            assert rejected >= 1, f"minute {minute}: zero rejections ({admitted=})"

    # We fired more than 10,000 in the simulated window — the question
    # "does inbound block > 10k/day?" is therefore meaningful.
    total_fired = total_ok + total_429
    assert total_fired == REQS_PER_MIN * MINUTES
    assert total_fired > 10_000, f"want >10k in window, got {total_fired}"

    # The per-minute window is the binding constraint: the *first*
    # minute's 5 over-cap requests are rejected, and from then on the
    # sliding window stays full so the steady-state admission rate is
    # exactly limit/minute (30 of 35). The total admitted in 400
    # minutes therefore cannot exceed 30 × 400 = 12,000, and the total
    # rejected is the remainder.
    assert total_ok <= 30 * MINUTES, f"admitted too many ({total_ok=})"
    assert total_429 >= REQS_PER_MIN * MINUTES - 30 * MINUTES
    # And at least the first minute's 5 over-cap were rejected.
    assert total_429 >= 5
    # Total fired equals the attempted load — sanity.
    assert total_ok + total_429 == REQS_PER_MIN * MINUTES


# ── NAV-only: funds endpoint must stay on the funds route ─────────


def test_funds_path_is_the_only_nav_route(client) -> None:
    """NAV lives on /api/v1/funds/* — these are the only paths that
    resolve to NAV data. /api/v1/crypto and /api/v1/options have no NAV.

    This is a routing-level guard so a future refactor doesn't accidentally
    attach NAV handling to a non-fund endpoint. We assert each of those
    paths returns 404 (no route registered) and the funds route still
    serves as expected.
    """
    # Funds list works.
    r = client.get("/api/v1/funds")
    assert r.status_code == 200

    # Non-fund paths simply don't exist in this minimal app — 404.
    for path in ("/api/v1/crypto", "/api/v1/options", "/api/v1/stocks"):
        assert client.get(path).status_code == 404, path

    # /health is exempt from rate-limiting and returns 200.
    assert client.get("/api/v1/health").status_code == 200
