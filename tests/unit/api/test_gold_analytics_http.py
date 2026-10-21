"""HTTP contract for ``/api/v1/gold/analytics``.

Every route is a pure calculator mounted from ``services/gold``; these tests
pin the published paths, response envelope and validation behavior.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from core.security.tokens import create_access_token

BASE = "/api/v1/gold/analytics"


@pytest.fixture()
def auth_headers() -> dict[str, str]:
    """Writes under ``/api/v1/gold/`` are gated by SecurityMiddleware."""
    token = create_access_token({"sub": "tester", "roles": ["user"], "type": "access"})
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture()
def client(app, auth_headers) -> TestClient:
    test_client = TestClient(app, raise_server_exceptions=False)
    test_client.headers.update(auth_headers)
    return test_client


def _post(client: TestClient, path: str, payload: dict) -> dict:
    response = client.post(f"{BASE}{path}", json=payload)
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["success"] is True, body
    return body["data"]


def test_mesghal_to_gram18(client: TestClient) -> None:
    data = _post(client, "/physical/mesghal", {"mesghal_price": 1_000_000})
    assert data["gram18_price"] == pytest.approx(230_850.80989389637, rel=1e-9)


def test_assay_adjustment(client: TestClient) -> None:
    data = _post(
        client,
        "/physical/assay",
        {"weight_grams": 10, "assay": 705, "base_gram18_price": 5_000_000},
    )
    assert data["real_weight_gram18"] == pytest.approx(9.4)
    assert data["value_irr"] == pytest.approx(47_000_000)


def test_coin_bubbles(client: TestClient) -> None:
    data = _post(
        client,
        "/physical/coin-bubbles",
        {
            "ounce_usd": 2_000,
            "usd_irr": 1_000_000,
            "coin_prices": {"emami": 500_000_000, "gerami": 60_000_000},
        },
    )
    assert data["emami"]["intrinsic_value_irr"] == pytest.approx(
        470_714_710.7878512, rel=1e-9
    )
    assert data["gerami"]["minting_fee_irr"] == pytest.approx(15_000)
    assert data["emami"]["bubble_pct"] > 0


def test_ime_vs_melted_arbitrage(client: TestClient) -> None:
    data = _post(
        client,
        "/physical/ime-arbitrage",
        {"ime_cert_price_irr": 7_000_000, "melted_gram18_price_irr": 5_000_000},
    )
    assert data["melted_equivalent_fine_irr"] == pytest.approx(6_633_333.333333333)
    assert data["action"] == "BUY_MELTED_SELL_IME_CERT"


def test_black76_price_and_greeks(client: TestClient) -> None:
    data = _post(
        client,
        "/options/black76",
        {"F": 100, "K": 90, "T": 0.5, "r": 0.03, "sigma": 0.25, "option_type": "call"},
    )
    assert data["price"] == pytest.approx(12.6499787281, abs=1e-9)
    assert data["greeks"]["delta"] == pytest.approx(0.7419251180, abs=1e-9)


def test_implied_volatility_round_trip(client: TestClient) -> None:
    data = _post(
        client,
        "/options/implied-volatility",
        {
            "market_price": 12.6499787281,
            "F": 100,
            "K": 90,
            "T": 0.5,
            "r": 0.03,
            "option_type": "call",
        },
    )
    assert data["implied_volatility"] == pytest.approx(0.25, rel=1e-6)


def test_pcr(client: TestClient) -> None:
    data = _post(
        client,
        "/options/pcr",
        {
            "options_chain": [
                {"strike": 100, "option_type": "call", "volume": 10, "open_interest": 20},
                {"strike": 100, "option_type": "put", "volume": 20, "open_interest": 5},
            ]
        },
    )
    assert data["pcr_volume"] == pytest.approx(2.0)
    assert data["pcr_oi"] == pytest.approx(0.25)


def test_max_pain(client: TestClient) -> None:
    data = _post(
        client,
        "/options/max-pain",
        {
            "options_chain": [
                {"strike": 90, "option_type": "call", "open_interest": 100},
                {"strike": 100, "option_type": "call", "open_interest": 100},
                {"strike": 110, "option_type": "call", "open_interest": 10},
                {"strike": 90, "option_type": "put", "open_interest": 10},
                {"strike": 100, "option_type": "put", "open_interest": 100},
                {"strike": 110, "option_type": "put", "open_interest": 100},
            ]
        },
    )
    assert data["max_pain_strike"] == pytest.approx(100.0)


def test_enrich_chain(client: TestClient) -> None:
    data = _post(
        client,
        "/options/enrich",
        {
            "options_chain": [
                {
                    "strike": 90,
                    "option_type": "call",
                    "market_price": 12.6499787281,
                }
            ],
            "forward_price": 100,
            "risk_free_rate": 0.03,
            "days_to_expiry": 182.5,
        },
    )
    row = data["contracts"][0]
    assert row["iv"] == pytest.approx(0.25, rel=1e-6)
    assert row["moneyness"] == pytest.approx(100 / 90)
    assert row["delta"] == pytest.approx(0.7419251180, abs=1e-6)


def test_futures_term_structure(client: TestClient) -> None:
    data = _post(
        client,
        "/futures/term-structure",
        {
            "spot_price": 100,
            "contracts": [
                {"contract_symbol": "F1", "futures_price": 150, "days_to_expiry": 365}
            ],
        },
    )
    assert data["n_contracts"] == 1
    assert data["curve_structure"] == "CONTANGO"
    assert data["contracts"][0]["market_state"] == "CONTANGO"
    assert data["contracts"][0]["arbitrage_signal"] == "CARRY_ARBITRAGE_OPPORTUNITY"
    assert data["threshold_yield"] == pytest.approx(0.31)


def test_aed_parity_signal(client: TestClient) -> None:
    data = _post(
        client,
        "/macro/aed-parity",
        {"aed_rate": 1_000_000, "tehran_usd_rate": 3_800_000},
    )
    assert data["dubai_implied_usd"] == pytest.approx(3_672_500)
    assert data["is_flagged"] is True
    assert data["signal"] == "TEHRAN_GOLD_REPRICING_RISK"


def test_macro_posture(client: TestClient) -> None:
    data = _post(
        client,
        "/macro/posture",
        {"tips_yield": 0.8, "dxy_index": 92, "gold_trend": "up"},
    )
    assert data["posture"] == "BULLISH"
    assert data["composite_score"] == pytest.approx(3)


def test_invalid_payload_is_422(client: TestClient) -> None:
    response = client.post(f"{BASE}/physical/mesghal", json={"mesghal_price": -1})
    assert response.status_code == 422


def test_invalid_option_type_is_422(client: TestClient) -> None:
    response = client.post(
        f"{BASE}/options/black76",
        json={"F": 100, "K": 100, "T": 0.5, "r": 0.03, "sigma": 0.2, "option_type": "x"},
    )
    assert response.status_code == 422
    assert "option_type" in response.json()["detail"]
