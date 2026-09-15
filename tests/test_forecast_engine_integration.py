"""تست ادغام BrsApi_Forecasting — ایمن، بدون شکستن API فعلی."""

from __future__ import annotations


def test_symbol_registry_imports():
    from src.forecast_engine.symbol_registry import (
        SYMBOL_REGISTRY,
        all_intraday_eligible_symbols,
        is_fair_value_applicable,
    )

    assert "gold_18k" in SYMBOL_REGISTRY
    assert "usd_irr_free" in SYMBOL_REGISTRY
    assert is_fair_value_applicable("gold_18k") is True
    assert is_fair_value_applicable("coin_emami") is False
    assert len(all_intraday_eligible_symbols()) >= 20


def test_config_constants():
    from src.forecast_engine.config import EMA_PERIOD, TROY_OUNCE_GRAMS, VALID_RANGES

    assert EMA_PERIOD == 14
    assert 31 < TROY_OUNCE_GRAMS < 32
    assert "XAU_USD" in VALID_RANGES


def test_fair_value_calculation():
    from src.forecast_engine.forecasting_service import calculate_fair_value

    # gold_18k purity 0.75, xau=2000, usd=800000 → per gram = 2000*800000/31.1 ≈ 51M *0.75 ≈ 38M
    fv = calculate_fair_value("gold_18k", 2000, 800_000)
    assert 30_000_000 < fv < 50_000_000


def test_project_from_closes_requires_real_history():
    import pytest

    from src.forecasting.service import project_from_closes

    # Fabricating a forecast from too little data must be refused.
    with pytest.raises(ValueError):
        project_from_closes("gold_18k", [100.0, 101.0], 7)

    closes = [100 + i * 0.5 for i in range(30)]
    result = project_from_closes("gold_18k", closes, 7)
    assert result["symbol"] == "gold_18k"
    assert len(result["forecast"]) == 7
    assert result["meta"]["history_points"] == 30
    assert result["model"]["name"] == "statistical_baseline"


def test_safe_forecast_isolation():
    import asyncio

    from src.forecast_engine.safe_forecast import safe_forecast_many

    async def ok_fn(s: str):
        return {"symbol": s, "forecasted_price": 100}

    async def fail_fn(s: str):
        if s == "bad":
            raise ValueError("bad input")
        return {"symbol": s, "forecasted_price": 100}

    async def _run():
        r1 = await safe_forecast_many(["gold_18k", "bad"], fail_fn)
        assert r1["gold_18k"].ok is True
        assert r1["bad"].ok is False
        assert r1["bad"].error_code == "invalid_input"

        r2 = await safe_forecast_many(["gold_18k"], ok_fn)
        assert r2["gold_18k"].ok is True

    asyncio.run(_run())


def test_router_includes_forecast_engine():
    from apps.api.router import Router

    r = Router().setup()
    paths = [route.path for route in r.routes]
    # باید هر دو /forecast و /forecast-engine mount شده باشند
    assert any("/forecast" in p for p in paths)
    assert any("forecast-engine" in p for p in paths)


def test_existing_forecast_endpoint_is_honest():
    from fastapi.testclient import TestClient

    from apps.api.app import create_app

    app = create_app()
    client = TestClient(app)
    resp = client.get("/api/v1/forecast?symbol=gold_18k&horizon=7&last_close=81200000")
    assert resp.status_code == 200
    data = resp.json()
    # The endpoint must either return a real-history forecast or a clear error —
    # never silently fabricated numbers.
    if data["success"]:
        assert data["data"]["forecast"]
        assert data["data"]["quality"]["history_points"] >= 20
    else:
        assert data["error"] and data["error"]["message"]


def test_new_engine_symbols_endpoint():
    from fastapi.testclient import TestClient

    from apps.api.app import create_app

    app = create_app()
    client = TestClient(app)
    resp = client.get("/api/v1/forecast-engine/symbols")
    assert resp.status_code == 200
    j = resp.json()
    assert j["success"] is True
    assert "gold_18k" in j["data"]
