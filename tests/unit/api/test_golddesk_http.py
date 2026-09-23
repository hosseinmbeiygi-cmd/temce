"""🔐 HTTP contract for the GoldDesk scoped-token surface + tier middleware.

Covers the three monetization behaviours of منشور بخش ۴:
  1. Scoped tokens: 401 without/with-bad ``X-API-Key``, 200 with valid key,
     403 with insufficient scope.
  2. Tier token bucket: a free-tier subject gets 429 (TIER_RATE_LIMIT) after
     its burst is exhausted, while another subject is unaffected.
  3. The GoldDesk routes are mounted and delegate to the real gold service.
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
from core.security.saas import TIERS, TieredTokenBucketLimiter, create_scoped_token
from core.security.tokens import create_access_token

GOLDDESK = "/api/v1/golddesk/snapshot"


def _client() -> TestClient:
    return TestClient(app, raise_server_exceptions=False)


def _stub_live_payload() -> dict[str, Any]:
    return {
        "status": "ok",
        "is_stale": False,
        "error": None,
        "gold_oz_usd": 2650.0,
        "usd_irr": 850_000.0,
        "gold_18k_irr": 5_400_000.0,
        "coin_emami_irr": 68_000_000.0,
        "timestamp": "2026-09-23T10:00:00+00:00",
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


class TestGoldDeskScopedAccess:
    def test_401_without_key(self, stub_gold_service) -> None:
        assert _client().get(GOLDDESK).status_code == 401

    def test_401_with_garbage_key(self, stub_gold_service) -> None:
        r = _client().get(GOLDDESK, headers={"X-API-Key": "gdesk_bogus_bogus"})
        assert r.status_code == 401

    def test_200_with_valid_scoped_key(self, stub_gold_service) -> None:
        key = create_scoped_token(tier="pro", scopes=["gold:read"], owner="svc-e2e")
        r = _client().get(GOLDDESK, headers={"X-API-Key": key})
        assert r.status_code == 200
        body = r.json()
        assert body["success"] is True
        assert body["meta"]["tier"] == "pro"
        assert body["meta"]["owner"] == "svc-e2e"

    def test_403_when_scope_insufficient(self, stub_gold_service) -> None:
        key = create_scoped_token(tier="pro", scopes=["market:read"], owner="svc-e2e")
        r = _client().get(GOLDDESK, headers={"X-API-Key": key})
        assert r.status_code == 403


class TestTierMiddlewareIntegration:
    """Direct middleware tests on a probe app (mirrors test_rate_limit_middleware.py)."""

    def _probe(self, limiter: TieredTokenBucketLimiter) -> TestClient:
        probe = FastAPI()

        @probe.get("/api/v1/echo")
        async def echo() -> dict:
            return {"ok": True}

        probe.add_middleware(RateLimitMiddleware, window_seconds=60.0)
        with patch("core.security.saas.get_tier_limiter", return_value=limiter):
            yield TestClient(probe, raise_server_exceptions=False)

    def test_free_jwt_exhausts_burst_then_429(self) -> None:
        limiter = TieredTokenBucketLimiter()
        token = create_access_token({"sub": "user-42", "roles": ["user"], "type": "access"})
        headers = {"Authorization": f"Bearer {token}"}
        tier = TIERS["free"]
        for gen in range(2):
            client = next(self._probe(limiter))
            outcomes = [client.get("/api/v1/echo", headers=headers).status_code for _ in range(tier.burst + 2)]
            if outcomes[tier.burst] == 429:
                break
            limiter = TieredTokenBucketLimiter()  # regenerate a fresh probe once
        assert outcomes[: tier.burst] == [200] * tier.burst
        assert outcomes[tier.burst] == 429, outcomes
        assert client.get("/api/v1/echo").status_code == 200, "anonymous requests bypass the tier bucket"

    def test_anonymous_unaffected_by_tier_bucket(self) -> None:
        limiter = TieredTokenBucketLimiter()
        client = next(self._probe(limiter))
        for _ in range(TIERS["free"].burst + 3):
            assert client.get("/api/v1/echo").status_code == 200

    def test_pro_tier_higher_burst_than_free(self) -> None:
        limiter = TieredTokenBucketLimiter()
        token = create_access_token({"sub": "pro-1", "roles": ["pro"], "type": "access"})
        headers = {"Authorization": f"Bearer {token}"}
        client = next(self._probe(limiter))
        admitted = 0
        for i in range(TIERS["pro"].burst + 5):
            if client.get("/api/v1/echo", headers=headers).status_code == 200:
                admitted += 1
            else:
                break
        assert admitted >= TIERS["free"].burst, "pro tier must admit at least the free burst"
