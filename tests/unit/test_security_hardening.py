"""Tests for the security-hardening additions:

1. CSRFMiddleware — same-origin enforcement for unsafe methods
2. JWT jti revocation — create/revoke/check blacklist via the cache
3. Prometheus /metrics route — text exposition served by the app
"""

from __future__ import annotations

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from apps.api.metrics import MetricsMiddleware, get_prometheus_exporter
from apps.api.middleware import CSRFMiddleware
from core.cache import CacheService
from core.config import settings


class _FakeRedis:
    """Minimal dict-backed redis stub with the methods CacheService uses."""

    def __init__(self) -> None:
        self._store: dict[str, str] = {}

    async def ping(self) -> bool:
        return True

    async def get(self, key: str):
        return self._store.get(key)

    async def setex(self, key: str, ttl: int, value: str) -> None:
        self._store[key] = value

    async def set(self, key: str, value: str) -> None:
        self._store[key] = value

    async def delete(self, key: str) -> None:
        self._store.pop(key, None)


@pytest.fixture
def connected_cache(monkeypatch):
    """Provide a CacheService backed by an in-memory fake Redis."""
    cache = CacheService(redis_url="redis://localhost:6379/15")
    cache._redis = _FakeRedis()
    # tokens.py imports get_cache lazily inside functions, so patching the
    # source module attribute is enough.
    monkeypatch.setattr("core.cache.get_cache", lambda: cache)
    return cache


def _create_csrf_app() -> FastAPI:
    app = FastAPI()
    app.add_middleware(CSRFMiddleware)

    @app.post("/api/v1/auth/login")
    async def login():
        return {"ok": True}

    @app.get("/api/v1/signals")
    async def signals():
        return {"ok": True}

    return app


@pytest.fixture(autouse=True)
def _restrict_cors_origins():
    """Pin CORS origins to a fixed list for deterministic CSRF tests.

    The real .env uses ["*"] (dev), which makes CSRF a no-op by design —
    the tests need a concrete origin allowlist instead.
    """
    original = settings.cors_origins
    settings.cors_origins = ["http://localhost:3000"]
    yield
    settings.cors_origins = original


def _create_metrics_app() -> FastAPI:
    app = FastAPI()
    app.add_middleware(MetricsMiddleware)

    @app.get("/api/v1/signals")
    async def signals():
        return {"ok": True}

    @app.post("/api/v1/signals")
    async def create_signal():
        return {"ok": True}

    @app.get("/metrics")
    async def metrics():
        from fastapi.responses import PlainTextResponse
        return PlainTextResponse(
            get_prometheus_exporter().export_text(),
            media_type="text/plain; version=0.0.4",
        )

    return app


# ════════════════════════════════════════════════════════════════
# CSRF Middleware
# ════════════════════════════════════════════════════════════════


class TestCSRFMiddleware:
    def test_safe_method_with_cross_origin_allowed(self):
        """GET with a cross-site Origin header is not blocked."""
        client = TestClient(_create_csrf_app(), raise_server_exceptions=False)
        res = client.get("/api/v1/signals", headers={"Origin": "https://evil.example.com"})
        assert res.status_code == 200

    def test_unsafe_method_no_origin_allowed(self):
        """POST without Origin/Referer (curl, server-to-server) passes."""
        client = TestClient(_create_csrf_app(), raise_server_exceptions=False)
        res = client.post("/api/v1/auth/login")
        assert res.status_code == 200

    def test_unsafe_method_allowed_origin(self):
        """POST with an allowed CORS origin passes."""
        client = TestClient(_create_csrf_app(), raise_server_exceptions=False)
        res = client.post("/api/v1/auth/login", headers={"Origin": "http://localhost:3000"})
        assert res.status_code == 200

    def test_unsafe_method_referer_allowed(self):
        """POST with a same-host Referer (which includes a path) passes."""
        client = TestClient(_create_csrf_app(), raise_server_exceptions=False)
        res = client.post(
            "/api/v1/auth/login",
            headers={"Referer": "http://localhost:3000/some/page?q=1"},
        )
        assert res.status_code == 200

    def test_unsafe_method_cross_origin_blocked(self):
        """POST with a cross-site Origin is blocked with 403 + CSRF_BLOCKED."""
        client = TestClient(_create_csrf_app(), raise_server_exceptions=False)
        res = client.post("/api/v1/auth/login", headers={"Origin": "https://evil.example.com"})
        assert res.status_code == 403
        body = res.json()
        assert body["success"] is False
        assert body["code"] == "CSRF_BLOCKED"

    def test_unsafe_method_cross_site_referer_blocked(self):
        """POST with a cross-site Referer is blocked."""
        client = TestClient(_create_csrf_app(), raise_server_exceptions=False)
        res = client.post("/api/v1/auth/login", headers={"Referer": "https://evil.example.com/x"})
        assert res.status_code == 403


# ════════════════════════════════════════════════════════════════
# JWT jti revocation
# ════════════════════════════════════════════════════════════════


class TestTokenRevocation:
    @pytest.mark.asyncio
    async def test_create_token_has_jti(self):
        from core.security.tokens import create_access_token, decode_access_token

        token = create_access_token({"sub": "usr-1", "roles": ["admin"]})
        payload = decode_access_token(token)
        assert payload.get("jti"), "Access token must carry a unique jti claim"

    @pytest.mark.asyncio
    async def test_jti_unique_per_token(self):
        from core.security.tokens import create_access_token, decode_access_token

        t1 = decode_access_token(create_access_token({"sub": "usr-1"}))
        t2 = decode_access_token(create_access_token({"sub": "usr-1"}))
        assert t1["jti"] != t2["jti"]

    @pytest.mark.asyncio
    async def test_not_revoked_by_default(self, connected_cache):
        from core.security.tokens import create_access_token, decode_access_token, is_token_revoked

        token = create_access_token({"sub": "usr-1"})
        payload = decode_access_token(token)
        assert await is_token_revoked(payload["jti"]) is False

    @pytest.mark.asyncio
    async def test_revoked_after_revoke(self, connected_cache):
        from core.security.tokens import create_access_token, decode_access_token, is_token_revoked, revoke_token

        token = create_access_token({"sub": "usr-1"})
        payload = decode_access_token(token)
        await revoke_token(payload["jti"], ttl=60)
        assert await is_token_revoked(payload["jti"]) is True

    @pytest.mark.asyncio
    async def test_revoke_token_without_jti_is_noop(self, connected_cache):
        from core.security.tokens import is_token_revoked, revoke_token

        await revoke_token(None, ttl=60)
        assert await is_token_revoked(None) is False

    @pytest.mark.asyncio
    async def test_revoke_access_token_blacklists_jti(self, connected_cache):
        from core.security.tokens import (
            create_access_token,
            decode_access_token,
            is_token_revoked,
            revoke_access_token,
        )

        token = create_access_token({"sub": "usr-1"})
        payload = decode_access_token(token)
        await revoke_access_token(token)
        assert await is_token_revoked(payload["jti"]) is True

    @pytest.mark.asyncio
    async def test_revoke_invalid_token_is_safe(self, connected_cache):
        from core.security.tokens import revoke_access_token

        # Must not raise for a malformed token
        await revoke_access_token("not-a-real-jwt")


# ════════════════════════════════════════════════════════════════
# Prometheus /metrics
# ════════════════════════════════════════════════════════════════


class TestMetricsEndpoint:
    def test_metrics_text_format(self):
        client = TestClient(_create_metrics_app(), raise_server_exceptions=False)
        # Generate some traffic first
        client.get("/api/v1/signals")
        client.post("/api/v1/signals")

        res = client.get("/metrics")
        assert res.status_code == 200
        assert res.headers["content-type"].startswith("text/plain")
        text = res.text
        assert "http_requests_total" in text
        assert "http_request_duration_seconds" in text

    def test_counter_increments(self):
        exporter = get_prometheus_exporter()
        exporter.reset()
        exporter.inc("http_requests_total", labels={"method": "GET", "route": "/api/v1/signals"})
        exporter.inc("http_requests_total", labels={"method": "GET", "route": "/api/v1/signals"})
        text = exporter.export_text()
        assert 'http_requests_total{method=GET,route=/api/v1/signals} 2.0' in text

    def test_exporter_reset(self):
        exporter = get_prometheus_exporter()
        exporter.reset()
        assert exporter.export_text() == ""

    def test_disable_flag_then_reenable(self):
        """disable()/enable() toggle the internal flag without losing stored metrics."""
        exporter = get_prometheus_exporter()
        exporter.reset()
        exporter.inc("test_metric", value=5)
        exporter.disable()
        assert not exporter._enabled
        # Stored metrics are still exported after disable (metrics are frozen,
        # not cleared) — re-enable and reset for a clean slate.
        assert "test_metric" in exporter.export_text()
        exporter.enable()
        exporter.reset()
