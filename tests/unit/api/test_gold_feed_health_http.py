"""HTTP contract for ``GET /api/v1/gold/analytics/feed-health``.

The live provider check and the DB read are stubbed so these tests never
touch the network or a real database.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from apps.api.dependencies import get_db_session
from apps.api.endpoints import gold_analytics
from services.gold.macro_indicators import GoldFeedUnavailableError

BASE = "/api/v1/gold/analytics"


@pytest.fixture()
def client(app):
    async def _session():
        yield object()

    app.dependency_overrides[get_db_session] = _session
    yield TestClient(app, raise_server_exceptions=False)
    app.dependency_overrides.pop(get_db_session, None)


def _attempt(provider: str, status: str, ok: bool) -> dict:
    return {
        "provider": provider,
        "status": status,
        "ok": ok,
        "latency_ms": 12.5,
        "age_seconds": 3.0 if ok else None,
        "error": None if ok else "HTTP 500",
        "price": 2_400.0 if ok else None,
        "checked_at": "2026-10-18T00:00:00+00:00",
    }


def test_feed_health_returns_primary_and_recent_attempts(client, monkeypatch) -> None:
    async def fake_check(session):
        return {
            "check_id": "check-1",
            "checked_at": "2026-10-18T00:00:00+00:00",
            "ok": True,
            "provider": "brsapi",
            "price": 2_400.0,
            "fallback_used": False,
            "primary": _attempt("brsapi", "ok", True),
            "attempts": [_attempt("brsapi", "ok", True)],
        }

    async def fake_load(session, limit):
        assert limit == 20
        return [_attempt("brsapi", "ok", True)]

    monkeypatch.setattr(gold_analytics, "check_gold_feed_health", fake_check)
    monkeypatch.setattr(gold_analytics, "load_recent_feed_health_attempts", fake_load)

    response = client.get(f"{BASE}/feed-health")

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["success"] is True
    assert body["data"]["primary"]["status"] == "ok"
    assert body["data"]["attempts"][0]["provider"] == "brsapi"


def test_feed_health_returns_503_when_all_providers_fail(client, monkeypatch) -> None:
    attempts = [
        {"provider": "brsapi", "status": "error", "error": "HTTP 500"},
        {"provider": "yahoo", "status": "timeout", "error": "timed out after 5.0s"},
    ]

    async def fake_check(session):
        raise GoldFeedUnavailableError(attempts)

    async def fake_load(session, limit):
        return [_attempt("brsapi", "error", False), _attempt("yahoo", "timeout", False)]

    monkeypatch.setattr(gold_analytics, "check_gold_feed_health", fake_check)
    monkeypatch.setattr(gold_analytics, "load_recent_feed_health_attempts", fake_load)

    response = client.get(f"{BASE}/feed-health")

    assert response.status_code == 503, response.text
    body = response.json()
    assert body["success"] is False
    assert body["data"]["primary"]["status"] == "error"
    assert len(body["data"]["attempts"]) == 2


def test_feed_health_limit_is_validated(client) -> None:
    response = client.get(f"{BASE}/feed-health?limit=0")

    assert response.status_code == 422


def test_feed_health_is_public(client, monkeypatch) -> None:
    async def fake_check(session):
        return {
            "check_id": "check-1",
            "checked_at": "2026-10-18T00:00:00+00:00",
            "ok": True,
            "provider": "brsapi",
            "price": 2_400.0,
            "fallback_used": False,
            "primary": _attempt("brsapi", "ok", True),
            "attempts": [_attempt("brsapi", "ok", True)],
        }

    async def fake_load(session, limit):
        return [_attempt("brsapi", "ok", True)]

    monkeypatch.setattr(gold_analytics, "check_gold_feed_health", fake_check)
    monkeypatch.setattr(gold_analytics, "load_recent_feed_health_attempts", fake_load)

    bare = TestClient(client.app, raise_server_exceptions=False)
    response = bare.get(f"{BASE}/feed-health")

    assert response.status_code == 200, response.text
