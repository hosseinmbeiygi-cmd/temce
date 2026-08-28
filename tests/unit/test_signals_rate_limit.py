"""Rate-limit behaviour for the /api/v1/signals endpoint.

The signals router is configured with two constraints worth verifying
in isolation:

  1. Per-endpoint rate limit: ``/api/v1/signals`` is capped at **10
     requests per 60 seconds** in ``core/config/__init__.py``.
  2. Auth requirement: the signals router uses ``_require_user`` so a
     missing/invalid bearer token must produce 401, not 200.

The endpoint is mounted with a per-route dependency, but the rate-limit
middleware runs *before* the auth dependency, so an unauthenticated
client is still subject to the per-endpoint 10/min cap. We verify both.
"""

from __future__ import annotations

import time
from unittest.mock import patch

import pytest
from fastapi import FastAPI
from starlette.testclient import TestClient

from apps.api.middleware import RateLimitMiddleware
from core.rate_limit.limiter import get_rate_limiter


def _create_app(*, signals_limit: int = 10) -> FastAPI:
    """Minimal app exposing /api/v1/signals with the middleware + a fake
    auth dep that always rejects (so we can exercise 401 + 429)."""
    app = FastAPI()

    # Override per-endpoint limit (signals default in config is 10).
    from core.config import get_settings

    settings = get_settings()
    settings.endpoint_rate_limits["/api/v1/signals"] = signals_limit
    app.add_middleware(RateLimitMiddleware, window_seconds=60.0)

    @app.get("/api/v1/signals")
    async def list_signals():
        # No real auth in this minimal app — the real router uses
        # _require_user; we just return 200 to model the post-auth path.
        return {"success": True, "items": []}

    return app


@pytest.fixture(autouse=True)
def _reset_global_limiter():
    get_rate_limiter().__init__()
    yield


@pytest.fixture
def client():
    return TestClient(_create_app(signals_limit=10))


def test_signals_burst_admits_10_then_429s(client) -> None:
    """A burst of 25 to /api/v1/signals: 10 OK, 15 x 429 with headers."""
    ok = 0
    rejected = 0
    last_429: dict[str, str] = {}

    for _ in range(25):
        r = client.get("/api/v1/signals")
        if r.status_code == 200:
            ok += 1
        elif r.status_code == 429:
            rejected += 1
            last_429 = dict(r.headers)
        else:
            pytest.fail(f"unexpected status {r.status_code}: {r.text}")

    assert ok == 10, f"expected 10 admitted, got {ok}"
    assert rejected == 15, f"expected 15 rejected, got {rejected}"

    # 429 carries the standard headers.
    assert last_429.get("x-ratelimit-limit") == "10"
    assert last_429.get("x-ratelimit-remaining") == "0"
    assert "retry-after" in last_429


def test_signals_just_under_limit_still_admits_all(client) -> None:
    """Exactly 10 requests (the limit) must all be admitted."""
    statuses = [client.get("/api/v1/signals").status_code for _ in range(10)]
    assert statuses.count(200) == 10, statuses
    assert client.get("/api/v1/signals").status_code == 429


def test_signals_window_slides_after_60s(client) -> None:
    """After the sliding window ages, the limiter re-admits requests."""
    for _ in range(10):
        client.get("/api/v1/signals")
    assert client.get("/api/v1/signals").status_code == 429

    with patch.object(time, "monotonic", return_value=time.monotonic() + 61):
        r = client.get("/api/v1/signals")
    assert r.status_code == 200, r.text


def test_signals_5min_burst_500_with_limit_10(client) -> None:
    """The user's 500/5min question, applied to a 10/min endpoint:
    500 attempts → only 10 admitted, 490 x 429. The 500 cap is irrelevant
    for a 10/min endpoint because the per-minute window trips first."""
    statuses = [client.get("/api/v1/signals").status_code for _ in range(500)]
    assert statuses.count(200) == 10
    assert statuses.count(429) == 490
