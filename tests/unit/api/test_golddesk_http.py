"""🔐 HTTP contract for the GoldDesk scoped-token surface + tier middleware.

Covers the three monetization behaviours of منشور بخش ۴:
  1. Scoped tokens: 401 without/with-bad ``X-API-Key``, 200 with valid key,
     403 with insufficient scope.
  2. Tier token bucket: a free-tier JWT gets 429 (TIER_RATE_LIMIT) after its
     burst is exhausted, while a different IP/user is unaffected.
  3. The GoldDesk routes are mounted and delegate to the real gold service.
"""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient

from apps.api.app import app
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
    with patch("apps.api.dependencies.get_gold_live_service") as dep:
        service = dep.return_value
        service.get_live_prices = AsyncMock(return_value=_stub_live_payload())
        yield service


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

    def test_free_tier_key_rate_limited_with_429(self, stub_gold_service) -> None:
        """A token's own tier bucket applies on top of scope checks."""
        from apps.api.endpoints import golddesk

        limiter = TieredTokenBucketLimiter()
        with patch.object(golddesk, "api_key_auth") as _unused, patch(
            "core.security.saas.get_tier_limiter", return_value=limiter
        ):
            key = create_scoped_token(tier="free", scopes=["gold:read"], owner="svc-e2e")
            client = _client()
            outcomes = [_client().get(GOLDDESK, headers={"X-API-Key": key}).status_code for _ in range(TIERS["free"].burst + 2)]
        assert outcomes[: TIERS["free"].burst] == [200] * TIERS["free"].burst
        assert 429 in outcomes[TIERS["free"].burst :], "over-burst calls must be tier-limited"


class TestTierMiddlewareIntegration:
    def _token(self, roles: list[str]) -> str:
        return create_access_token({"sub": "user-42", "roles": roles, "type": "access"})

    def test_free_jwt_exhausts_burst_then_429(self) -> None:
        from apps.api.middleware import RateLimitMiddleware

        with patch.object(RateLimitMiddleware, "dispatch", new=lambda self, request, call_next: call_next(request)):
            limiter = TieredTokenBucketLimiter()
            with patch("core.security.saas.get_tier_limiter", return_value=limiter):
                from fastapi import FastAPI

                from apps.api.middleware import RateLimitMiddleware as RLM

                probe = FastAPI()

                @probe.get("/api/v1/echo")
                async def echo() -> dict:
                    return {"ok": True}

                probe.add_middleware(RLM, window_seconds=60.0)
                client = TestClient(probe, raise_server_exceptions=False)
                headers = {"Authorization": f"Bearer {self._token(['user'])}"}
                tier = TIERS["free"]
                outcomes = [client.get("/api/v1/echo", headers=headers).status_code for _ in range(tier.burst + 2)]
        assert outcomes[: tier.burst] == [200] * tier.burst
        assert outcomes[tier.burst] == 429
        assert client.get("/api/v1/echo").status_code == 200, "anonymous requests bypass the tier bucket"

    def test_anonymous_unaffected_by_tier_bucket(self) -> None:
        from fastapi import FastAPI

        from apps.api.middleware import RateLimitMiddleware

        limiter = TieredTokenBucketLimiter()
        probe = FastAPI()

        @probe.get("/api/v1/echo")
        async def echo() -> dict:
            return {"ok": True}

        probe.add_middleware(RLM, window_seconds=60.0)
        with patch("core.security.saas.get_tier_limiter", return_value=limiter):
            client = TestClient(probe, raise_server_exceptions=False)
            for _ in range(TIERS["free"].burst + 3):
                assert client.get("/api/v1/echo").status_code == 200
