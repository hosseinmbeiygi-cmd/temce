"""HTTP contract for the Step 5 gold derivatives endpoints."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from apps.api.endpoints import gold_analytics
from core.security.tokens import create_access_token

BASE = "/api/v1/gold/analytics"


@pytest.fixture()
def auth_headers() -> dict[str, str]:
    token = create_access_token({"sub": "tester", "roles": ["user"], "type": "access"})
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture()
def client(app, auth_headers) -> TestClient:
    test_client = TestClient(app, raise_server_exceptions=False)
    test_client.headers.update(auth_headers)
    return test_client


def test_options_chain_get_uses_service(monkeypatch, client: TestClient) -> None:
    captured: dict = {}

    async def fake_report(session, **kwargs):
        captured.update(kwargs)
        return {
            "available": True,
            "contracts": [{"contract_key": "C1", "iv": 0.25}],
            "iv_term_structure": [],
            "skew_by_expiry": [],
        }

    monkeypatch.setattr(gold_analytics, "get_options_chain_report", fake_report)
    response = client.get(
        f"{BASE}/options/chain",
        params={
            "commodity": "GOLD",
            "limit": 5,
            "forward_price": 100.0,
            "risk_free_rate": 0.03,
            "min_volume": 10,
        },
    )

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["success"] is True
    assert body["data"]["contracts"][0]["contract_key"] == "C1"
    assert captured["commodity"] == "GOLD"
    assert captured["limit"] == 5
    assert captured["forward_price"] == pytest.approx(100.0)
    assert captured["risk_free_rate"] == pytest.approx(0.03)
    assert captured["liquidity_thresholds"] == {"min_volume": 10}


def test_options_chain_requires_jwt(app, monkeypatch, auth_headers) -> None:
    """STEP 7D-1: IV rank/percentile, skew and term structure are derived
    analytics, so the chain read is no longer anonymous."""

    async def fake_report(session, **kwargs):
        return {
            "available": True,
            "contracts": [],
            "iv_term_structure": [],
            "skew_by_expiry": [],
        }

    monkeypatch.setattr(gold_analytics, "get_options_chain_report", fake_report)
    public_client = TestClient(app, raise_server_exceptions=False)
    response = public_client.get(f"{BASE}/options/chain")
    assert response.status_code == 401, response.text

    authed = TestClient(app, raise_server_exceptions=False, headers=auth_headers)
    assert authed.get(f"{BASE}/options/chain").status_code == 200


def test_options_strategy_post_hand_computed(client: TestClient) -> None:
    response = client.post(
        f"{BASE}/options/strategy",
        json={
            "strategy": "straddle",
            "legs": [
                {
                    "option_type": "call",
                    "strike": 100.0,
                    "quantity": 1.0,
                    "premium": 5.0,
                    "iv": 0.25,
                },
                {
                    "option_type": "put",
                    "strike": 100.0,
                    "quantity": 1.0,
                    "premium": 4.0,
                    "iv": 0.30,
                },
            ],
            "expiry_price": 100.0,
            "forward_price": 100.0,
            "risk_free_rate": 0.03,
            "days_to_expiry": 30.0,
            "pre_expiry_days": 15.0,
            "pre_expiry_forward": 105.0,
        },
    )

    assert response.status_code == 200, response.text
    data = response.json()["data"]
    assert data["net_debit"] == pytest.approx(9.0)
    assert data["expiry_pnl"] == pytest.approx(-9.0)
    assert data["breakevens"] == pytest.approx([91.0, 109.0])
    assert data["max_loss"] == pytest.approx(9.0)
    assert data["max_profit"] is None
    assert data["max_profit_unbounded"] is True
    assert data["pre_expiry_value"] is not None


def test_options_strategy_post_requires_auth(app) -> None:
    public_client = TestClient(app, raise_server_exceptions=False)
    response = public_client.post(
        f"{BASE}/options/strategy",
        json={
            "strategy": "straddle",
            "legs": [
                {
                    "option_type": "call",
                    "strike": 100.0,
                    "quantity": 1.0,
                    "premium": 5.0,
                }
            ],
            "expiry_price": 100.0,
        },
    )
    assert response.status_code in (401, 403), response.text


def test_options_strategy_validation_is_422(client: TestClient) -> None:
    response = client.post(
        f"{BASE}/options/strategy",
        json={
            "strategy": "straddle",
            "legs": [
                {
                    "option_type": "butterfly",
                    "strike": 100.0,
                    "quantity": 1.0,
                    "premium": 5.0,
                }
            ],
            "expiry_price": 100.0,
        },
    )
    assert response.status_code == 422
    assert "option_type" in response.json()["detail"]


def test_options_margin_post_hand_computed(client: TestClient) -> None:
    response = client.post(
        f"{BASE}/options/margin",
        json={
            "entry_price": 100.0,
            "prices": [100.0, 95.0, 94.0, 90.0],
            "direction": 1,
            "quantity": 1.0,
            "config": {
                "initial_margin_ratio": 0.10,
                "maintenance_margin_ratio": 0.05,
                "margin_call_equity_ratio": 1.00,
                "stop_out_equity_ratio": 0.50,
                "contract_size": 10.0,
                "contract_multiplier": 1.0,
            },
        },
    )

    assert response.status_code == 200, response.text
    data = response.json()["data"]
    assert data["status"] == "ok"
    assert data["margin_call_index"] == 2
    assert data["stop_out_index"] == 3
    assert data["steps"][2]["event"] == "MARGIN_CALL"
    assert data["steps"][3]["event"] == "STOP_OUT"


def test_options_margin_not_configured_is_reported(client: TestClient) -> None:
    response = client.post(
        f"{BASE}/options/margin",
        json={"entry_price": 100.0, "prices": [100.0], "config": {}},
    )
    assert response.status_code == 200, response.text
    data = response.json()["data"]
    assert data["status"] == "not_configured"
    assert data["configured"] is False
