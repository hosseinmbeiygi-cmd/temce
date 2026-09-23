"""🔐 SaaS tiering contract tests: per-user token buckets + scoped API tokens.

منشور (بخش ۴):
  1. Rate limiting based on user tiers (Free / Pro / Institutional) with a
     token-bucket refill algorithm — NOT the flat per-IP sliding window alone.
  2. Scoped API tokens: key format ``gdesk_<tier>_<scopeless-random>``, each
     carrying a tier, an explicit scope list and an owner; scope enforcement
     happens in HTTP-space (401 without key, 403 with insufficient scope).

These tests define the contract BEFORE the implementation exists (TDD-AO).
"""

from __future__ import annotations

import pytest
from fastapi import Depends, FastAPI, HTTPException
from fastapi.testclient import TestClient

from core.rate_limit.tokens import TokenBucket
from core.security.saas import (
    SCOPES,
    TIERS,
    ScopedToken,
    ScopedTokenError,
    TieredTokenBucketLimiter,
    api_key_auth,
    create_scoped_token,
    require_scopes,
    resolve_tier,
    verify_scoped_token,
)

# ─────────────────────────────────────────────────────────────────────
# Part 1 — Token bucket math (algorithmic contract)
# ─────────────────────────────────────────────────────────────────────


class TestTokenBucketMath:
    def test_burst_is_immediately_available(self) -> None:
        bucket = TokenBucket(rate=10.0, burst=5)
        for _ in range(5):
            assert bucket.acquire_sync() == 0.0
        assert bucket.acquire_sync() > 0.0

    def test_refill_rate_is_linear(self) -> None:
        bucket = TokenBucket(rate=10.0, burst=1)
        bucket.acquire_sync()
        bucket.acquire_sync()  # empties the bucket; wait = 1/10 = 0.1s
        assert abs(bucket.acquire_sync() - 0.1) < 0.02

    def test_capacity_never_exceeded(self) -> None:
        bucket = TokenBucket(rate=10.0, burst=3)
        for _ in range(50):
            bucket.acquire_sync()
        assert bucket.tokens <= bucket.burst

    def test_invalid_config_rejected(self) -> None:
        with pytest.raises(ValueError):
            TokenBucket(rate=0.0, burst=1)


@pytest.mark.asyncio
async def test_bucket_async_acquire_matches_sync() -> None:
    bucket = TokenBucket(rate=10.0, burst=2)
    assert await bucket.acquire() == 0.0
    assert await bucket.acquire() == 0.0
    assert await bucket.acquire() > 0.0


class TestTieredLimiter:
    def test_tiers_have_distinct_limits(self) -> None:
        assert TIERS["free"].rpm < TIERS["pro"].rpm < TIERS["institutional"].rpm
        assert TIERS["free"].burst < TIERS["institutional"].burst

    def test_resolve_tier_from_jwt_roles(self) -> None:
        assert resolve_tier(["user"]) == "free"
        assert resolve_tier(["user", "pro"]) == "pro"
        assert resolve_tier(["admin"]) == "institutional"
        assert resolve_tier([]) == "free"

    def test_free_tier_bucket_exhausts_then_rejects(self) -> None:
        limiter = TieredTokenBucketLimiter()
        tier = TIERS["free"]
        for _ in range(tier.burst):
            assert limiter.allow("u1", tier), "fresh bucket must admit the full burst"
        assert not limiter.allow("u1", tier), "empty bucket must reject"

    def test_isolated_buckets_per_user(self) -> None:
        limiter = TieredTokenBucketLimiter()
        tier = TIERS["free"]
        for _ in range(tier.burst):
            assert limiter.allow("u1", tier)
        assert not limiter.allow("u1", tier)
        assert limiter.allow("u2", tier), "users must have independent buckets"


# ─────────────────────────────────────────────────────────────────────
# Part 2 — Scoped API tokens
# ─────────────────────────────────────────────────────────────────────


class TestScopedTokenLifecycle:
    def test_roundtrip_preserves_claims(self) -> None:
        raw = create_scoped_token(tier="pro", scopes=["market:read", "options:read"], owner="svc-alpha")
        tok = verify_scoped_token(raw)
        assert tok.tier == "pro"
        assert list(tok.scopes) == ["market:read", "options:read"]
        assert tok.owner == "svc-alpha"

    def test_key_prefix_is_gdesk(self) -> None:
        raw = create_scoped_token(tier="free", scopes=["market:read"], owner="o")
        assert raw.startswith("gdesk_")

    def test_tampered_key_rejected(self) -> None:
        raw = create_scoped_token(tier="pro", scopes=["market:read"], owner="o")
        bad = raw[:-4] + ("aaaa" if not raw.endswith("aaaa") else "bbbb")
        with pytest.raises(ScopedTokenError):
            verify_scoped_token(bad)

    def test_garbage_rejected(self) -> None:
        with pytest.raises(ScopedTokenError):
            verify_scoped_token("not-a-real-key")
        with pytest.raises(ScopedTokenError):
            verify_scoped_token("")

    def test_unknown_scope_rejected_at_creation(self) -> None:
        with pytest.raises(ValueError):
            create_scoped_token(tier="pro", scopes=["make:money"], owner="o")

    def test_unknown_tier_rejected_at_creation(self) -> None:
        with pytest.raises(ValueError):
            create_scoped_token(tier="platinum", scopes=["market:read"], owner="o")

    def test_expiry_enforced(self) -> None:
        raw = create_scoped_token(tier="pro", scopes=["market:read"], owner="o", ttl_days=-1)
        with pytest.raises(ScopedTokenError):
            verify_scoped_token(raw)

    def test_scoped_token_is_dataclass(self) -> None:
        tok = verify_scoped_token(create_scoped_token(tier="free", scopes=["market:read"], owner="o"))
        assert isinstance(tok, ScopedToken)


class TestScopeEnforcement:
    def test_scopes_catalog_shape(self) -> None:
        assert "market:read" in SCOPES
        assert all(":" in s for s in SCOPES)

    def test_require_scopes_all_pass(self) -> None:
        dep = require_scopes("market:read", "options:read")
        tok = verify_scoped_token(
            create_scoped_token(tier="institutional", scopes=["market:read", "options:read"], owner="o")
        )
        assert dep(tok) is tok

    def test_require_scopes_insufficient_is_403(self) -> None:
        dep = require_scopes("admin:write")
        tok = verify_scoped_token(create_scoped_token(tier="pro", scopes=["market:read"], owner="o"))
        with pytest.raises(HTTPException) as ei:
            dep(tok)
        assert ei.value.status_code == 403


class TestHTTPWiring:
    def _client(self) -> TestClient:
        app = FastAPI()

        @app.get("/gdesk/snapshot", dependencies=[Depends(api_key_auth("market:read"))])
        async def snapshot() -> dict:
            return {"ok": True}

        @app.get("/gdesk/admin", dependencies=[Depends(api_key_auth("admin:write"))])
        async def admin() -> dict:
            return {"ok": True}

        return TestClient(app, raise_server_exceptions=False)

    def test_401_without_key(self) -> None:
        c = self._client()
        assert c.get("/gdesk/snapshot").status_code == 401

    def test_200_with_valid_key(self) -> None:
        raw = create_scoped_token(tier="pro", scopes=["market:read"], owner="svc")
        c = self._client()
        r = c.get("/gdesk/snapshot", headers={"X-API-Key": raw})
        assert r.status_code == 200

    def test_403_scope_missing(self) -> None:
        raw = create_scoped_token(tier="pro", scopes=["market:read"], owner="svc")
        c = self._client()
        r = c.get("/gdesk/admin", headers={"X-API-Key": raw})
        assert r.status_code == 403


# ─────────────────────────────────────────────────────────────────────
# Part 3 — Tier limits integration
# ─────────────────────────────────────────────────────────────────────


class TestTierLimitsIntegration:
    def test_free_burst_exhausts_and_recovers_with_time(self) -> None:
        limiter = TieredTokenBucketLimiter()
        tier = TIERS["free"]
        results = [limiter.allow("u9", tier) for _ in range(tier.burst + 3)]
        assert results[: tier.burst] == [True] * tier.burst
        assert not any(results[tier.burst :]), "over-burst requests must be rejected"

        # Fake the clock forward past a full refill period and retry.
        limiter.advance_time(tier.refill_seconds + 0.05)
        assert limiter.allow("u9", tier), "bucket must refill over time"

    def test_institutional_burst_larger_than_free(self) -> None:
        limiter = TieredTokenBucketLimiter()
        inst = TIERS["institutional"]
        admitted = sum(limiter.allow("inst-1", inst) for _ in range(inst.burst))
        assert admitted == inst.burst
