"""HTTP contract for the cached physical-market analytics routes.

The service layer is stubbed, so these tests pin paths, query validation,
response envelopes and public (GET) access without touching a database or
network.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from apps.api.dependencies import get_db_session
from apps.api.endpoints import gold_analytics
from core.security.tokens import create_access_token

BASE = "/api/v1/gold/analytics"


@pytest.fixture()
def auth_headers() -> dict[str, str]:
    """STEP 7D-1: bubbles, arbitrage and the AED series are signal-bearing
    reads, so they now resolve to a real user."""
    token = create_access_token({"sub": "analyst", "roles": ["user"], "type": "access"})
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture()
def client(app, auth_headers):
    async def _session():
        yield object()

    app.dependency_overrides[get_db_session] = _session
    test_client = TestClient(app, raise_server_exceptions=False)
    test_client.headers.update(auth_headers)
    yield test_client
    app.dependency_overrides.pop(get_db_session, None)


def test_coins_endpoint_returns_coin_report(client, monkeypatch) -> None:
    seen: dict[str, object] = {}

    async def fake(session, history_limit=200):
        seen["history_limit"] = history_limit
        return {
            "available": True,
            "history_limit": history_limit,
            "coins": {"emami": {"bubble_pct": 6.22, "bubble_abs_irr": 29_285_289.21}},
        }

    monkeypatch.setattr(gold_analytics, "get_coin_bubble_report", fake)

    response = client.get(f"{BASE}/coins?history_limit=25")

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["success"] is True
    assert body["data"]["coins"]["emami"]["bubble_pct"] == pytest.approx(6.22)
    assert seen["history_limit"] == 25


def test_arbitrage_endpoint_returns_spread_and_limit_check(client, monkeypatch) -> None:
    seen: dict[str, object] = {}

    async def fake(
        session,
        quantity_grams=1.0,
        holding_days=0,
        storage_irr_per_gram_per_day=None,
        delivery_irr_per_gram=None,
    ):
        seen.update(
            quantity_grams=quantity_grams,
            holding_days=holding_days,
            storage=storage_irr_per_gram_per_day,
            delivery=delivery_irr_per_gram,
        )
        return {
            "available": True,
            "action": "NO_ARBITRAGE",
            "net_spread_pct": -0.29,
            "limit_check": {"ok": None, "status": "not_configured", "violations": []},
        }

    monkeypatch.setattr(gold_analytics, "get_ime_arbitrage_report", fake)

    response = client.get(
        f"{BASE}/arbitrage?quantity_grams=2&holding_days=3"
        "&storage_irr_per_gram_per_day=1000&delivery_irr_per_gram=5000"
    )

    assert response.status_code == 200, response.text
    data = response.json()["data"]
    assert data["action"] == "NO_ARBITRAGE"
    assert data["limit_check"]["status"] == "not_configured"
    assert seen == {
        "quantity_grams": 2.0,
        "holding_days": 3,
        "storage": 1000.0,
        "delivery": 5000.0,
    }


def test_aed_history_endpoint_returns_series_and_alert(client, monkeypatch) -> None:
    seen: dict[str, object] = {}

    async def fake(session, limit=200):
        seen["limit"] = limit
        return {
            "available": True,
            "series": [
                {"snapshot_at": "t1", "spread_pct": 1.0, "z_score": None, "alert": False}
            ],
            "current": {"spread_pct": 1.0, "z_score": None, "alert": False},
            "alert_zscore": 2.0,
        }

    monkeypatch.setattr(gold_analytics, "get_aed_history_report", fake)

    response = client.get(f"{BASE}/aed-history?limit=10")

    assert response.status_code == 200, response.text
    data = response.json()["data"]
    assert data["available"] is True
    assert data["current"]["alert"] is False
    assert seen["limit"] == 10


def test_physical_reports_require_jwt(client, monkeypatch) -> None:
    """STEP 7D-1: coin bubbles, the arbitrage spread and the AED z-score series
    are platform-derived analytics, so anonymous callers no longer get them.
    The authenticated cases are covered by the tests above via ``client``."""
    async def coins(session, history_limit=200):
        return {"available": True, "coins": {}}

    async def arbitrage(
        session,
        quantity_grams=1.0,
        holding_days=0,
        storage_irr_per_gram_per_day=None,
        delivery_irr_per_gram=None,
    ):
        return {"available": True, "action": "NO_ARBITRAGE"}

    async def aed(session, limit=200):
        return {"available": True, "series": [], "current": None}

    monkeypatch.setattr(gold_analytics, "get_coin_bubble_report", coins)
    monkeypatch.setattr(gold_analytics, "get_ime_arbitrage_report", arbitrage)
    monkeypatch.setattr(gold_analytics, "get_aed_history_report", aed)

    bare = TestClient(client.app, raise_server_exceptions=False)

    for path in ("/coins", "/arbitrage", "/aed-history"):
        response = bare.get(f"{BASE}{path}")
        assert response.status_code == 401, f"{path} -> {response.status_code}"


def test_empty_data_is_reported_without_fabrication(client, monkeypatch) -> None:
    async def coins(session, history_limit=200):
        return {
            "available": False,
            "reason": "XAUUSD price unavailable",
            "coins": {},
            "missing_symbols": ["XAUUSD"],
        }

    monkeypatch.setattr(gold_analytics, "get_coin_bubble_report", coins)

    response = client.get(f"{BASE}/coins")

    assert response.status_code == 200, response.text
    data = response.json()["data"]
    assert data["available"] is False
    assert data["coins"] == {}
    assert data["reason"] == "XAUUSD price unavailable"


@pytest.mark.parametrize(
    "path",
    [
        f"{BASE}/coins?history_limit=0",
        f"{BASE}/coins?history_limit=1001",
        f"{BASE}/arbitrage?quantity_grams=0",
        f"{BASE}/arbitrage?holding_days=-1",
        f"{BASE}/arbitrage?storage_irr_per_gram_per_day=-1",
        f"{BASE}/arbitrage?delivery_irr_per_gram=-1",
        f"{BASE}/aed-history?limit=0",
        f"{BASE}/aed-history?limit=2001",
    ],
)
def test_query_validation_is_422(client, path) -> None:
    response = client.get(path)

    assert response.status_code == 422, response.text
