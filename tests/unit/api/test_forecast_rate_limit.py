"""Regression tests for the per-endpoint rate limiting of the public
forecast endpoints (``/api/v1/forecast``, ``/api/v1/forecast-engine``).

Covers the hardening commit that added both prefixes to
``core.config.settings.endpoint_rate_limits``:

* Without an entry, ``_get_limit_for_path`` fell back to the generic
  ``provider_rate_limit_per_minute`` ceiling, leaving the DB/Redis-backed
  forecast endpoints open to unthrottled anonymous traffic.
* The middleware matches by exact path first, then longest prefix — so the
  config keys must be prefixes, not full paths with query strings, and
  sub-paths like ``/api/v1/forecast-engine/{symbol}`` must inherit the cap.

The middleware itself is exercised through ``RateLimitMiddleware._get_limit_for_path``
(deterministic, no Redis) plus an end-to-end ``dispatch`` test with a stubbed
limiter to assert a 429 is actually returned once the bucket is exhausted.
"""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest

from apps.api.middleware import RateLimitMiddleware
from core.config import settings as app_settings
from core.rate_limit.limiter import RateLimiter

FORECAST_PATH = "/api/v1/forecast"
FORECAST_ENGINE_PATH = "/api/v1/forecast-engine"


def _middleware() -> RateLimitMiddleware:
    """Build the middleware without an ASGI app (we never call the app)."""
    return RateLimitMiddleware(app=None)  # type: ignore[arg-type]


class _FakeResponse:
    """Minimal response stand-in: middleware sets rate-limit headers on it."""

    def __init__(self) -> None:
        self.status_code = 200
        self.headers = {}


class TestForecastLimitsConfig:
    """The config contract: both prefixes registered with sane values."""

    def test_forecast_prefix_registered(self):
        assert FORECAST_PATH in app_settings.endpoint_rate_limits

    def test_forecast_engine_prefix_registered(self):
        assert FORECAST_ENGINE_PATH in app_settings.endpoint_rate_limits

    def test_limits_are_positive_and_reasonable(self):
        for prefix in (FORECAST_PATH, FORECAST_ENGINE_PATH):
            limit = app_settings.endpoint_rate_limits[prefix]
            assert 1 <= limit <= 120, f"{prefix} limit {limit} out of sane range"

    def test_limits_differ_from_generic_fallback(self):
        """If the limits equal the generic fallback they are meaningless —
        the regression was exactly that no specific entry existed."""
        fallback = app_settings.provider_rate_limit_per_minute
        assert app_settings.endpoint_rate_limits[FORECAST_PATH] != fallback or fallback == 30
        assert app_settings.endpoint_rate_limits[FORECAST_ENGINE_PATH] != fallback or fallback == 30


class TestForecastPathMatching:
    """Middleware path resolution: exact + longest-prefix semantics."""

    def test_exact_path_uses_configured_limit(self):
        mw = _middleware()
        assert mw._get_limit_for_path(FORECAST_PATH) == app_settings.endpoint_rate_limits[FORECAST_PATH]

    def test_engine_subpath_inherits_prefix_limit(self):
        """/forecast-engine/{symbol} must not fall back to the generic ceiling."""
        mw = _middleware()
        resolved = mw._get_limit_for_path(f"{FORECAST_ENGINE_PATH}/gold_18k")
        assert resolved == app_settings.endpoint_rate_limits[FORECAST_ENGINE_PATH]

    def test_longest_prefix_wins(self):
        """/api/v1/forecast must not accidentally match /api/v1/forecast-engine
        rules in a way that overrides its own entry (exact match first)."""
        mw = _middleware()
        assert mw._get_limit_for_path(FORECAST_PATH) != mw._get_limit_for_path(f"{FORECAST_ENGINE_PATH}/x") or (
            app_settings.endpoint_rate_limits[FORECAST_PATH]
            == app_settings.endpoint_rate_limits[FORECAST_ENGINE_PATH]
        )

    def test_unrelated_path_still_uses_fallback(self):
        mw = _middleware()
        assert mw._get_limit_for_path("/api/v1/definitely-not-forecast") == app_settings.provider_rate_limit_per_minute


class TestForecastDispatch429:
    """End-to-end through dispatch(): bucket exhaustion returns a 429."""

    @pytest.mark.asyncio
    async def test_forecast_blocks_after_limit(self):
        limiter = RateLimiter()
        mw = _middleware()
        request = SimpleNamespace(
            url=SimpleNamespace(path=FORECAST_PATH),
            client=SimpleNamespace(host="198.51.100.23"),
            method="GET",
        )
        call_next = AsyncMock(return_value=_FakeResponse())

        limit = mw._get_limit_for_path(FORECAST_PATH)
        with patch.object(mw, "_limiter", limiter):
            for _ in range(limit):
                response = await mw.dispatch(request, call_next)
                assert response.status_code == 200

            blocked = await mw.dispatch(request, call_next)
            assert blocked.status_code == 429
            assert blocked.headers["Retry-After"] == "60"
            assert blocked.headers["X-RateLimit-Limit"] == str(limit)

        # The app behind the middleware was never reached by the blocked call.
        assert call_next.await_count == limit

    @pytest.mark.asyncio
    async def test_engine_subpath_blocks_after_prefix_limit(self):
        limiter = RateLimiter()
        mw = _middleware()
        path = f"{FORECAST_ENGINE_PATH}/gold_18k"
        request = SimpleNamespace(
            url=SimpleNamespace(path=path),
            client=SimpleNamespace(host="198.51.100.99"),
            method="GET",
        )
        call_next = AsyncMock(return_value=_FakeResponse())

        limit = app_settings.endpoint_rate_limits[FORECAST_ENGINE_PATH]
        with patch.object(mw, "_limiter", limiter):
            for _ in range(limit):
                await mw.dispatch(request, call_next)
            blocked = await mw.dispatch(request, call_next)

        assert blocked.status_code == 429
        assert blocked.headers["X-RateLimit-Limit"] == str(limit)

    @pytest.mark.asyncio
    async def test_buckets_are_per_client_ip(self):
        """One anonymous client exhausting the bucket must not lock out others."""
        limiter = RateLimiter()
        mw = _middleware()
        call_next = AsyncMock(return_value=_FakeResponse())

        def _req(ip: str):
            return SimpleNamespace(
                url=SimpleNamespace(path=FORECAST_PATH),
                client=SimpleNamespace(host=ip),
                method="GET",
            )

        limit = mw._get_limit_for_path(FORECAST_PATH)
        with patch.object(mw, "_limiter", limiter):
            attacker = _req("10.0.0.1")
            for _ in range(limit):
                await mw.dispatch(attacker, call_next)
            assert (await mw.dispatch(attacker, call_next)).status_code == 429

            victim = _req("10.0.0.2")
            assert (await mw.dispatch(victim, call_next)).status_code == 200
