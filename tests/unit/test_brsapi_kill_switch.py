"""Unit tests for the BrsApi kill switch and fail-fast budget enforcement.

Background
----------
The user's BrsApi key got blocked because the platform exceeded the plan's
real request cap (~5,000/day). Two safety mechanisms were added:

1. ``BRSAPI_ENABLED=false`` — master kill switch. The client performs NO live
   HTTP request and returns a clear error instead (the platform keeps working
   from the database only, while the key stays blocked).

2. Fail-fast on daily budget exhaustion — when the global daily quota is used
   up and ``fail_fast_on_daily_exhausted`` is enabled, ``fetch()`` rejects the
   request immediately instead of sleeping until Tehran midnight (which used
   to pile up blocked-key cascades).

These tests lock in that neither path ever touches the network.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

import brsapi.client as client_mod
from brsapi.client import BrsApiClient
from brsapi.rate_limiter import RateLimiter


@pytest.fixture(autouse=True)
def _force_live_mode() -> None:
    """Default these tests to enabled mode.

    The real ``.env`` currently sets ``BRSAPI_ENABLED=false`` (DB-only mode
    while the key is blocked). Tests that exercise fetch/health normally
    assume the API is on; the kill-switch tests themselves patch
    ``enabled=False`` explicitly, which overrides this default.
    """
    with patch.object(client_mod.brsapi_settings, "enabled", True):
        yield


class _FakeResp:
    def __init__(self, status_code: int, content: bytes = b"{}"):
        self.status_code = status_code
        self.content = content
        self.text = "fake"
        self.headers = {}

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        return False


class _FakeEndpoint:
    path = "/Test/Endpoint.php"
    category = type("Cat", (), {"value": "tsetmc"})()
    default_params = {}


def _make_client(rate_limiter: RateLimiter | None = None) -> BrsApiClient:
    client = BrsApiClient(api_key="test", base_url="http://test.local",
                          rate_limiter=rate_limiter)
    client._client = AsyncMock()
    client._max_retries = 3
    return client


@pytest.mark.asyncio
async def test_kill_switch_disabled_rejects_without_http() -> None:
    """BRSAPI_ENABLED=false → fetch() fails cleanly, zero HTTP calls."""
    client = _make_client()
    with patch.object(client_mod.brsapi_settings, "enabled", False):
        result = await client.fetch(_FakeEndpoint())
    assert result.success is False
    assert "BRSAPI_ENABLED=false" in (result.error or "")
    assert "DB-only" in (result.error or "")
    client._client.get.assert_not_awaited()


@pytest.mark.asyncio
async def test_kill_switch_health_reports_disabled() -> None:
    """health() must surface the DB-only mode without hitting the network."""
    client = _make_client()
    with patch.object(client_mod.brsapi_settings, "enabled", False):
        health = await client.health()
    assert health["enabled"] is False
    assert health["reachable"] is False
    assert "BRSAPI_ENABLED=false" in (health.get("error") or "")
    client._client.get.assert_not_awaited()


@pytest.mark.asyncio
async def test_fail_fast_when_daily_budget_exhausted() -> None:
    """Daily quota used up → fetch() rejects immediately, no HTTP, no sleep."""
    limiter = RateLimiter(daily_limit=2, five_min_limit=500)
    await limiter.acquire("tsetmc")
    await limiter.acquire("tsetmc")  # exhaust the daily budget

    client = _make_client(rate_limiter=limiter)
    with patch.object(client_mod.brsapi_settings, "fail_fast_on_daily_exhausted", True):
        result = await client.fetch(_FakeEndpoint())
    assert result.success is False
    assert "daily budget exhausted" in (result.error or "").lower()
    client._client.get.assert_not_awaited()


@pytest.mark.asyncio
async def test_budget_available_requests_proceed() -> None:
    """With budget remaining the request goes through normally (no false block)."""
    client = _make_client()
    client._client.get = AsyncMock(return_value=_FakeResp(200, b'{"ok": true}'))
    with patch("asyncio.sleep", new=AsyncMock()):
        result = await client.fetch(_FakeEndpoint())
    assert result.success is True
    assert client._client.get.await_count == 1


@pytest.mark.asyncio
async def test_302_heavy_file_redirect_fails_fast_without_retry() -> None:
    """BrsApi anti-abuse: when server-side usage is above the plan threshold,
    every live call returns 302 to a massive file (e.g. Windows ISO). The
    client must fail fast with a clear quota message, never follow the
    redirect and never retry."""
    client = _make_client()
    resp = _FakeResp(302)
    resp.headers = {"Location": "https://cdn.example/Windows.11.part1.rar"}
    client._client.get = AsyncMock(return_value=resp)
    with patch("asyncio.sleep", new=AsyncMock()):
        result = await client.fetch(_FakeEndpoint())
    assert result.success is False
    assert "quota exceeded" in (result.error or "").lower()
    assert "302" in (result.error or "")
    assert client._client.get.await_count == 1  # no retry, no download


@pytest.mark.asyncio
async def test_acquire_fail_fast_raises_on_exhausted_budget() -> None:
    """Direct ``acquire()`` callers (e.g. HistoryFetchService) must also reject
    fast when the daily budget is gone — not sleep until Tehran midnight."""
    from brsapi.rate_limiter import RateLimitExhaustedError

    limiter = RateLimiter(daily_limit=1, five_min_limit=500, fail_fast=True)
    await limiter.acquire("tsetmc")
    with pytest.raises(RateLimitExhaustedError):
        await limiter.acquire("tsetmc")


@pytest.mark.asyncio
async def test_acquire_fail_fast_off_still_sleeps() -> None:
    """Without fail-fast the limiter keeps its legacy wait-until-midnight
    behaviour (only the wait is what fail-fast replaces)."""
    limiter = RateLimiter(daily_limit=1, five_min_limit=500, fail_fast=False)
    await limiter.acquire("tsetmc")
    # would block until midnight — assert the wait is > 0 instead of raising
    wait = limiter._wait_time_for_global_limits()
    assert wait > 0
    assert wait < 24 * 3600 + 60


@pytest.mark.asyncio
async def test_status_surfaces_remaining_budget() -> None:
    """status() must expose the daily remaining counter the fail-fast reads."""
    limiter = RateLimiter(daily_limit=10, five_min_limit=100)
    await limiter.acquire("tsetmc", endpoint="/Test/Endpoint.php")
    status = limiter.status()
    assert status["global"]["daily_count"] == 1
    assert status["global"]["daily_remaining"] == 9
    assert status["global"]["daily_limit"] == 10
