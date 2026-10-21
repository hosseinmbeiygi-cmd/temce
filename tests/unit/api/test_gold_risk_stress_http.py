"""HTTP contract for the gold portfolio stress-test endpoints."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

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


def _coin(exposure_irr: float = 500_000_000) -> dict:
    return {
        "symbol": "IR_COIN_EMAMI",
        "asset_type": "coin",
        "direction": "long",
        "exposure_irr": exposure_irr,
    }


def test_risk_scenarios_are_public(app) -> None:
    public_client = TestClient(app, raise_server_exceptions=False)
    response = public_client.get(f"{BASE}/risk/scenarios")

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["success"] is True
    ids = [row["scenario_id"] for row in body["data"]]
    assert len(ids) == 8
    assert ids[0] == "usd_spike"
    assert "black_swan" in ids
    assert set(body["data"][0]["shocks"]) == {
        "xau_usd_pct",
        "usd_irr_pct",
        "local_premium_pct",
        "fund_discount_pct",
        "volatility_points",
        "liquidity_haircut_pct",
    }


def test_risk_stress_black_swan_is_hand_computed(client: TestClient) -> None:
    response = client.post(
        f"{BASE}/risk/stress",
        json={
            "equity_irr": 1_000_000_000,
            "positions": [_coin()],
            "scenarios": [
                {
                    "scenario_id": "black_swan",
                    "name_fa": "شوک سیاه",
                    "name_en": "Black swan",
                    "shocks": {
                        "xau_usd_pct": -0.18,
                        "usd_irr_pct": 0.25,
                        "local_premium_pct": -0.12,
                        "fund_discount_pct": -0.10,
                        "volatility_points": 0.20,
                        "liquidity_haircut_pct": 0.15,
                    },
                }
            ],
        },
    )

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["success"] is True
    data = body["data"]
    assert data["risk_level"] == "HIGH"
    assert data["worst_case"]["scenario_id"] == "black_swan"
    assert data["worst_case"]["pnl_irr"] == pytest.approx(-122_500_000)
    assert data["worst_case"]["pnl_pct_of_equity"] == pytest.approx(-12.25)
    assert data["worst_case"]["post_equity_irr"] == pytest.approx(877_500_000)


def test_risk_stress_defaults_to_builtin_scenarios(client: TestClient) -> None:
    response = client.post(
        f"{BASE}/risk/stress",
        json={"equity_irr": 1_000_000_000, "positions": [_coin()]},
    )

    assert response.status_code == 200, response.text
    data = response.json()["data"]
    assert len(data["scenarios"]) == 8
    assert data["gross_exposure_irr"] == pytest.approx(500_000_000)
    assert data["gross_leverage_ratio"] == pytest.approx(0.5)


def test_risk_stress_custom_scenario(client: TestClient) -> None:
    response = client.post(
        f"{BASE}/risk/stress",
        json={
            "equity_irr": 1_000_000_000,
            "positions": [_coin()],
            "scenarios": [
                {
                    "scenario_id": "xau_rally",
                    "shocks": {"xau_usd_pct": 0.10},
                }
            ],
        },
    )

    assert response.status_code == 200, response.text
    row = response.json()["data"]["scenarios"][0]
    assert row["name_fa"] == "xau_rally"
    assert row["pnl_irr"] == pytest.approx(50_000_000)
    assert row["pnl_pct_of_equity"] == pytest.approx(5.0)


def test_risk_stress_requires_auth(app) -> None:
    public_client = TestClient(app, raise_server_exceptions=False)
    response = public_client.post(
        f"{BASE}/risk/stress",
        json={"equity_irr": 1_000_000_000, "positions": [_coin()]},
    )
    assert response.status_code in (401, 403), response.text


def test_risk_stress_rejects_zero_equity(client: TestClient) -> None:
    response = client.post(
        f"{BASE}/risk/stress",
        json={"equity_irr": 0, "positions": [_coin()]},
    )
    assert response.status_code == 422


def test_risk_stress_rejects_unknown_asset_type(client: TestClient) -> None:
    response = client.post(
        f"{BASE}/risk/stress",
        json={
            "equity_irr": 1_000_000_000,
            "positions": [{**_coin(), "asset_type": "bond"}],
        },
    )
    assert response.status_code == 422
