"""🔐 HTTP contract for the GoldDesk scoped-token surface + tier middleware.

Covers the three monetization behaviours of منشور بخش ۴:
  1. Scoped tokens: 401 without/with-bad ``X-API-Key``, 200 with valid key,
     403 with insufficient scope.
  2. Tier token bucket: a free-tier subject gets 429 (TIER_RATE_LIMIT) after
     its burst is exhausted, while anonymous requests are unaffected.
  3. The GoldDesk routes are mounted and delegate to the real gold service.

The real app (``apps.api.app``) is used so the mount + dependency wiring is
validated end to end (mirrors test_pre_buy_http.py). DB/gold-service are
stubbed via ``app.dependency_overrides`` — these tests assert *who may call
what*, not what the handlers compute.

Env isolation: ``app_settings.environment`` is forced to something other than
"test" for the duration of each request-context test so the per-IP sliding
window (skipped in test env) actually runs inside the middleware.
"""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from apps.api.app import app
from apps.api.dependencies import get_gold_live_service
from apps.api.middleware import RateLimitMiddleware
from core.config import settings as app_settings
from core.rate_limit.limiter import RateLimiter
from core.security.saas import (
    TIERS,
    TieredTokenBucketLimiter,
    create_scoped_token,
)
from core.security.tokens import create_access_token

GOLDDESK = "/api/v1/golddesk/snapshot"


def _client() -> TestClient:
    return TestClient(app, raise_server_exceptions=False)


def _stub_live_payload() -> dict[str, Any]:
    """Must satisfy the ``GoldLivePrices`` response schema — the delegated gold
    handler wraps the service payload in ``ApiResponse[GoldLivePrices]``."""
    return {
        "gold_oz_usd": 2650.0,
        "usd_irr": 850_000.0,
        "gold_18k_irr": 5_400_000.0,
        "coin_bahar_irr": 68_000_000.0,
        "last_updated": "2026-09-23T10:00:00+00:00",
        "source": "BrsApi.ir",
        "is_stale": False,
    }


@pytest.fixture()
def stub_gold_service():
    mock_service = AsyncMock()
    mock_service.get_live_prices = AsyncMock(return_value=_stub_live_payload())

    async def _override() -> Any:
        return mock_service

    app.dependency_overrides[get_gold_live_service] = _override
    yield mock_service
    app.dependency_overrides.pop(get_gold_live_service, None)


@pytest.fixture()
def _bypass_ip_window():
    """Pin env to "test" so the IP/tier middleware is bypassed deterministically.

    The scoped-token tests exercise ``api_key_auth`` (its own tier bucket in
    ``core.security.saas``) — middleware behaviour is covered by the probe-app
    tests below.
    """
    with patch.object(app_settings, "environment", "test"):
        yield


# ════════════════════════════════════════════════════════════════
# 1. Scoped-token HTTP contract on the real app
# ════════════════════════════════════════════════════════════════


class TestGoldDeskScopedAccess:
    def test_401_without_key(self, stub_gold_service, _bypass_ip_window) -> None:
        assert _client().get(GOLDDESK).status_code == 401

    def test_401_with_garbage_key(self, stub_gold_service, _bypass_ip_window) -> None:
        r = _client().get(GOLDDESK, headers={"X-API-Key": "gdesk_bogus_bogus"})
        assert r.status_code == 401

    def test_200_with_valid_scoped_key(self, stub_gold_service, _bypass_ip_window) -> None:
        key = create_scoped_token(tier="pro", scopes=["gold:read"], owner="svc-e2e")
        r = _client().get(GOLDDESK, headers={"X-API-Key": key})
        assert r.status_code == 200
        body = r.json()
        assert body["success"] is True
        assert body["data"]["gold_oz_usd"] == 2650.0
        assert body["meta"]["tier"] == "pro"
        assert body["meta"]["owner"] == "svc-e2e"

    def test_403_when_scope_insufficient(self, stub_gold_service, _bypass_ip_window) -> None:
        key = create_scoped_token(tier="pro", scopes=["market:read"], owner="svc-e2e")
        r = _client().get(GOLDDESK, headers={"X-API-Key": key})
        assert r.status_code == 403

    def test_scoped_key_rate_limited_after_burst(self, stub_gold_service, _bypass_ip_window) -> None:
        """A scoped token carries its own tier bucket — exhausting it 429s."""
        key = create_scoped_token(tier="free", scopes=["gold:read"], owner="svc-e2e")
        client = _client()
        outcomes = [client.get(GOLDDESK, headers={"X-API-Key": key}).status_code for _ in range(TIERS["free"].burst + 3)]
        assert outcomes[: TIERS["free"].burst] == [200] * TIERS["free"].burst
        assert outcomes[TIERS["free"].burst] == 429
        assert outcomes[-1] == 429

    def test_nav_premium_and_arbitrage_scopes(self, stub_gold_service, _bypass_ip_window) -> None:
        read_key = create_scoped_token(tier="pro", scopes=["gold:read"], owner="svc-e2e")
        assert _client().get("/api/v1/golddesk/nav-premium", headers={"X-API-Key": read_key}).status_code == 200

        # arbitrage needs gold:analyze — a read-only token must get 403
        r = _client().get("/api/v1/golddesk/arbitrage", headers={"X-API-Key": read_key})
        assert r.status_code == 403

        analyze_key = create_scoped_token(tier="pro", scopes=["gold:read", "gold:analyze"], owner="svc-e2e")
        assert _client().get("/api/v1/golddesk/arbitrage", headers={"X-API-Key": analyze_key}).status_code == 200


# ════════════════════════════════════════════════════════════════
# 2. Tier middleware on a probe app (JWT bearer → per-user bucket)
# ═════════════════════════════════


class TestTierMiddlewareIntegration:
    """JWT subjects get a per-user token bucket on top of the IP window.

    Probe-app pattern (mirrors test_rate_limit_middleware.py): a minimal FastAPI
    app + real RateLimitMiddleware, with BOTH limiter factories patched at the
    middleware module (the middleware bound those symbols at import time).
    Each test gets fresh limiter state, so no cross-test bucket leakage.
    """

    def _probe(self) -> TestClient:
        probe = FastAPI()

        @probe.get("/api/v1/echo")
        async def echo() -> dict:
            return {"ok": True}

        probe.add_middleware(RateLimitMiddleware, window_seconds=60.0)
        return TestClient(probe, raise_server_exceptions=False)

    @pytest.fixture()
    def _fresh_limiters(self):
        with (
            patch("apps.api.middleware.get_rate_limiter", return_value=RateLimiter()),
            patch("apps.api.middleware.get_tier_limiter", return_value=TieredTokenBucketLimiter()),
            patch.object(app_settings, "environment", "development"),
        ):
            yield

    def test_free_jwt_exhausts_tier_bucket_then_429(self, _fresh_limiters) -> None:
        token = create_access_token({"sub": "user-42", "roles": ["user"], "type": "access"})
        headers = {"Authorization": f"Bearer {token}"}
        tier = TIERS["free"]
        client = self._probe()
        outcomes = [client.get("/api/v1/echo", headers=headers).status_code for _ in range(tier.burst + 2)]
        assert outcomes[: tier.burst] == [200] * tier.burst
        assert outcomes[tier.burst] == 429, outcomes
        body = client.get("/api/v1/echo", headers=headers).json()
        assert body["code"] == "TIER_RATE_LIMIT"
        assert body["tier"] == "free"

    def test_anonymous_unaffected_by_tier_bucket(self, _fresh_limiters) -> None:
        """No bearer token → no tier subject → IP window only."""
        client = self._probe()
        for _ in range(TIERS["free"].burst + 3):
            assert client.get("/api/v1/echo").status_code == 200

    def test_pro_tier_admits_more_than_free_burst(self, _fresh_limiters) -> None:
        token = create_access_token({"sub": "pro-1", "roles": ["pro"], "type": "access"})
        headers = {"Authorization": f"Bearer {token}"}
        client = self._probe()
        admitted = 0
        for _ in range(TIERS["free"].burst + 1):
            if client.get("/api/v1/echo", headers=headers).status_code == 200:
                admitted += 1
            else:
                break
        assert admitted == TIERS["free"].burst + 1, "pro must outlast the free burst"

    def test_tier_429_headers(self, _fresh_limiters) -> None:
        """A tier 429 surfaces Retry-After derived from the tier refill."""
        token = create_access_token({"sub": "user-77", "roles": ["user"], "type": "access"})
        headers = {"Authorization": f"Bearer {token}"}
        client = self._probe()
        for _ in range(TIERS["free"].burst):
            client.get("/api/v1/echo", headers=headers)
        r = client.get("/api/v1/echo", headers=headers)
        assert r.status_code == 429
        assert "Retry-After" in r.headers
        assert r.headers["X-RateLimit-Limit"] == str(TIERS["free"].burst)
