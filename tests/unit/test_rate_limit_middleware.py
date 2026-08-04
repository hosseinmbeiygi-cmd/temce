"""Tests for RateLimitMiddleware — sliding window, prefix matching, 429 response, headers."""

from __future__ import annotations

import time
from unittest.mock import patch

import pytest
from fastapi import FastAPI
from starlette.testclient import TestClient

from apps.api.middleware import RateLimitMiddleware
from core.rate_limit.limiter import RateLimiter

# ── App factory ──────────────────────────────────────────────────


def _create_app() -> FastAPI:
    """Create a minimal FastAPI app with RateLimitMiddleware for testing."""
    app = FastAPI()
    app.add_middleware(RateLimitMiddleware, window_seconds=60.0)

    @app.get("/api/v1/signals")
    async def signals():
        return {"ok": True}

    @app.get("/api/v1/signals/123")
    async def signal_detail():
        return {"ok": True}

    @app.get("/api/v1/backtests/run")
    async def backtests_run():
        return {"ok": True}

    @app.get("/api/v1/ml/train")
    async def ml_train():
        return {"ok": True}

    @app.get("/api/v1/chat")
    async def chat():
        return {"ok": True}

    @app.get("/api/v1/news")
    async def news():
        return {"ok": True}

    @app.get("/api/v1/unknown-endpoint")
    async def unknown():
        return {"ok": True}

    @app.get("/docs")
    async def docs():
        return {"ok": True}

    @app.get("/api/v1/health")
    async def health():
        return {"ok": True}

    @app.patch("/api/v1/alerts/{alert_id}")
    async def patch_alert(alert_id: int):
        return {"ok": True, "id": alert_id}

    @app.post("/api/v1/signals")
    async def post_signals():
        return {"ok": True}

    return app


@pytest.fixture(autouse=True)
def _reset_limiter():
    """Reset the global rate limiter state between tests."""
    limiter = RateLimitMiddleware.__new__(RateLimitMiddleware)
    limiter._limiter = RateLimiter()
    with patch("apps.api.middleware.get_rate_limiter", return_value=limiter._limiter):
        yield


@pytest.fixture
def client():
    """Create a test client with RateLimitMiddleware."""
    return TestClient(_create_app(), raise_server_exceptions=False)


# ════════════════════════════════════════════════════════════════
# 1. Sliding Window
# ════════════════════════════════════════════════════════════════


class TestSlidingWindow:
    """Verify the sliding-window rate limiting algorithm."""

    def test_allows_requests_under_limit(self, client: TestClient):
        """5 requests should all succeed (limit is 10/min for /signals)."""
        for _ in range(5):
            res = client.get("/api/v1/signals")
            assert res.status_code == 200

    def test_blocks_when_limit_exceeded(self, client: TestClient):
        """After 10 requests, the 11th should be blocked with 429."""
        for _ in range(10):
            client.get("/api/v1/signals")

        res = client.get("/api/v1/signals")
        assert res.status_code == 429

    def test_429_response_body(self, client: TestClient):
        """429 response should have correct JSON structure."""
        for _ in range(10):
            client.get("/api/v1/signals")

        res = client.get("/api/v1/signals")
        assert res.status_code == 429
        body = res.json()
        assert body["success"] is False
        assert body["code"] == "RATE_LIMIT"
        assert body["limit"] == 10
        assert body["window_seconds"] == 60

    def test_different_paths_independent(self, client: TestClient):
        """Rate limits are per-path — /signals and /chat have separate buckets."""
        # Exhaust /signals (limit 10)
        for _ in range(10):
            client.get("/api/v1/signals")

        # /chat (limit 20) should still work
        res = client.get("/api/v1/chat")
        assert res.status_code == 200

    def test_different_clients_independent(self):
        """Different client IPs get separate rate limit buckets.

        The middleware builds its rate-limit key as ``api:{client_ip}:{path}``.
        We create two separate apps (each with its own middleware + limiter) and
        patch ``request.client.host`` via the ASGI scope to simulate two IPs
        hitting the same endpoint on separate limiter instances — proving that
        keys ``api:10.0.0.1:/signals`` and ``api:10.0.0.2:/signals`` are
        independent.

        Since patching ``request.client`` through TestClient is unreliable, we
        instead directly test the limiter + key logic: register two keys, exhaust
        one, and verify the other is unaffected.
        """
        from core.rate_limit.limiter import RateLimiter

        limiter = RateLimiter()
        signals_limit = 10  # same as config
        window = 60.0

        # Register limits for both IPs on the same path
        key_a = "api:10.0.0.1:/api/v1/signals"
        key_b = "api:10.0.0.2:/api/v1/signals"
        for key in (key_a, key_b):
            limiter.set_limit(key, rate=signals_limit / window, burst=signals_limit, window_seconds=window)

        # --- Exhaust bucket A ---
        for _ in range(signals_limit):
            assert limiter.allow(key_a) is True
        assert limiter.allow(key_a) is False  # blocked

        # --- Bucket B is completely fresh ---
        for _ in range(signals_limit):
            assert limiter.allow(key_b) is True
        assert limiter.allow(key_b) is False

        # Verify remaining() works per-key
        assert limiter.remaining(key_a) == 0
        assert limiter.remaining(key_b) == 0

    def test_remaining_decreases_with_requests(self, client: TestClient):
        """X-RateLimit-Remaining should decrease with each request."""
        res1 = client.get("/api/v1/signals")
        assert res1.headers.get("X-RateLimit-Remaining") == "9"

        res2 = client.get("/api/v1/signals")
        assert res2.headers.get("X-RateLimit-Remaining") == "8"


# ════════════════════════════════════════════════════════════════
# 2. HTTP Method Coverage (PATCH, POST)
# ════════════════════════════════════════════════════════════════


class TestHttpMethodCoverage:
    """Verify rate limiting applies to ALL HTTP methods, not just GET."""

    def test_patch_is_rate_limited(self, client: TestClient):
        """PATCH requests should be rate-limited like GET/POST.

        /api/v1/alerts has limit=30 per config.
        """
        for _ in range(30):
            res = client.patch("/api/v1/alerts/1")
            assert res.status_code == 200

        res = client.patch("/api/v1/alerts/1")
        assert res.status_code == 429

    def test_patch_429_has_correct_body(self, client: TestClient):
        """PATCH 429 response should have correct JSON structure."""
        for _ in range(30):
            client.patch("/api/v1/alerts/1")

        res = client.patch("/api/v1/alerts/1")
        assert res.status_code == 429
        body = res.json()
        assert body["success"] is False
        assert body["code"] == "RATE_LIMIT"

    def test_patch_has_ratelimit_headers(self, client: TestClient):
        """PATCH responses should include rate limit headers."""
        res = client.patch("/api/v1/alerts/1")
        assert res.status_code == 200
        assert "X-RateLimit-Limit" in res.headers
        assert res.headers.get("X-RateLimit-Limit") == "30"
        assert "X-RateLimit-Remaining" in res.headers

    def test_post_is_rate_limited(self, client: TestClient):
        """POST requests should be rate-limited."""
        # /api/v1/signals (POST) uses limit 10
        for _ in range(10):
            res = client.post("/api/v1/signals")
            assert res.status_code == 200

        res = client.post("/api/v1/signals")
        assert res.status_code == 429

    def test_mixed_methods_share_path_bucket(self, client: TestClient):
        """GET and POST to the same path share the rate limit bucket."""
        # Exhaust 8 of 10 via GET
        for _ in range(8):
            client.get("/api/v1/signals")

        # POST should only have 2 remaining
        res = client.post("/api/v1/signals")
        assert res.status_code == 200
        assert res.headers.get("X-RateLimit-Remaining") == "1"

        res = client.post("/api/v1/signals")
        assert res.status_code == 200
        assert res.headers.get("X-RateLimit-Remaining") == "0"

        # 11th total request (regardless of method) should be blocked
        res = client.get("/api/v1/signals")
        assert res.status_code == 429


# ════════════════════════════════════════════════════════════════
# 3. Prefix Matching
# ════════════════════════════════════════════════════════════════


class TestPrefixMatching:
    """Verify the longest-prefix-match algorithm for rate limits."""

    def test_exact_match_takes_priority(self, client: TestClient):
        """/api/v1/signals has limit 10 (exact match), not the default 300."""
        for _ in range(10):
            client.get("/api/v1/signals")

        res = client.get("/api/v1/signals")
        assert res.status_code == 429

    def test_prefix_match_for_subpath(self, client: TestClient):
        """/api/v1/signals/123 matches /api/v1/signals prefix → limit 10."""
        for _ in range(10):
            client.get("/api/v1/signals/123")

        res = client.get("/api/v1/signals/123")
        assert res.status_code == 429

    def test_longer_prefix_wins(self, client: TestClient):
        """/api/v1/backtests/run has limit 5 (more specific than /api/v1/backtests/*)."""
        for _ in range(5):
            client.get("/api/v1/backtests/run")

        res = client.get("/api/v1/backtests/run")
        assert res.status_code == 429

    def test_unknown_path_uses_default(self, client: TestClient):
        """/api/v1/unknown-endpoint uses provider_rate_limit_per_minute (300)."""
        # 100 requests should all succeed (well under 300)
        for _ in range(100):
            res = client.get("/api/v1/unknown-endpoint")
            assert res.status_code == 200

    def test_expensive_endpoints_have_low_limits(self, client: TestClient):
        """/api/v1/ml/train has limit 2 — should block after 2 requests."""
        for _ in range(2):
            client.get("/api/v1/ml/train")

        res = client.get("/api/v1/ml/train")
        assert res.status_code == 429

    def test_generous_endpoints_have_high_limits(self, client: TestClient):
        """/api/v1/news has limit 60 — should allow many requests."""
        for _ in range(50):
            res = client.get("/api/v1/news")
            assert res.status_code == 200


# ════════════════════════════════════════════════════════════════
# 4. 429 Response Headers
# ════════════════════════════════════════════════════════════════


class Test429Headers:
    """Verify 429 responses include proper rate limit headers."""

    def test_429_has_retry_after(self, client: TestClient):
        """429 should include Retry-After header."""
        for _ in range(10):
            client.get("/api/v1/signals")

        res = client.get("/api/v1/signals")
        assert res.status_code == 429
        assert "Retry-After" in res.headers

    def test_429_has_x_ratelimit_limit(self, client: TestClient):
        """429 should include X-RateLimit-Limit header."""
        for _ in range(10):
            client.get("/api/v1/signals")

        res = client.get("/api/v1/signals")
        assert res.headers.get("X-RateLimit-Limit") == "10"

    def test_429_has_x_ratelimit_remaining_zero(self, client: TestClient):
        """429 should show X-RateLimit-Remaining = 0."""
        for _ in range(10):
            client.get("/api/v1/signals")

        res = client.get("/api/v1/signals")
        assert res.headers.get("X-RateLimit-Remaining") == "0"

    def test_429_has_x_ratelimit_reset(self, client: TestClient):
        """429 should include X-RateLimit-Reset header."""
        for _ in range(10):
            client.get("/api/v1/signals")

        res = client.get("/api/v1/signals")
        reset = res.headers.get("X-RateLimit-Reset")
        assert reset is not None
        assert int(reset) > int(time.time())


# ════════════════════════════════════════════════════════════════
# 5. Success Response Headers
# ════════════════════════════════════════════════════════════════


class TestSuccessHeaders:
    """Verify successful responses include rate limit headers."""

    def test_success_has_x_ratelimit_limit(self, client: TestClient):
        res = client.get("/api/v1/signals")
        assert res.status_code == 200
        assert res.headers.get("X-RateLimit-Limit") == "10"

    def test_success_has_x_ratelimit_remaining(self, client: TestClient):
        res = client.get("/api/v1/signals")
        assert res.status_code == 200
        assert "X-RateLimit-Remaining" in res.headers
        assert int(res.headers["X-RateLimit-Remaining"]) >= 0

    def test_success_has_x_ratelimit_reset(self, client: TestClient):
        res = client.get("/api/v1/signals")
        assert res.status_code == 200
        reset = res.headers.get("X-RateLimit-Reset")
        assert reset is not None
        assert int(reset) > int(time.time())


# ════════════════════════════════════════════════════════════════
# 6. Exempt Paths
# ════════════════════════════════════════════════════════════════


class TestExemptPaths:
    """Verify /docs, /openapi.json, /api/v1/health bypass rate limiting."""

    def test_docs_bypasses_rate_limit(self, client: TestClient):
        """Even with environment=test, /docs should pass through."""
        for _ in range(100):
            res = client.get("/docs")
            assert res.status_code == 200

    def test_health_bypasses_rate_limit(self, client: TestClient):
        for _ in range(100):
            res = client.get("/api/v1/health")
            assert res.status_code == 200


# ════════════════════════════════════════════════════════════════
# 7. Edge Cases
# ════════════════════════════════════════════════════════════════


class TestEdgeCases:
    """Verify edge cases in rate limiting."""

    def test_empty_path(self, client: TestClient):
        """Root path should respond without crashing."""
        res = client.get("/api/v1/health")
        assert res.status_code == 200

    def test_path_with_query_params(self, client: TestClient):
        """/api/v1/signals?foo=bar should use same bucket as /api/v1/signals."""
        for _ in range(10):
            client.get("/api/v1/signals?foo=bar")

        # Same path with different query should be blocked
        res = client.get("/api/v1/signals?baz=qux")
        assert res.status_code == 429

    def test_preserves_response_body(self, client: TestClient):
        """Rate limiting should not corrupt the response body."""
        res = client.get("/api/v1/signals")
        assert res.json() == {"ok": True}

    def test_many_endpoints_work(self, client: TestClient):
        """All defined endpoints should respond without crashes."""
        endpoints = [
            "/api/v1/signals",
            "/api/v1/backtests/run",
            "/api/v1/ml/train",
            "/api/v1/chat",
            "/api/v1/news",
            "/api/v1/unknown-endpoint",
            "/docs",
            "/api/v1/health",
        ]
        for ep in endpoints:
            res = client.get(ep)
            assert res.status_code in (200, 307), f"Endpoint {ep} returned {res.status_code}"
