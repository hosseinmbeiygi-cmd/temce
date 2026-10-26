"""Integration tests for GoldDesk API endpoints."""

from __future__ import annotations

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient


def _make_app() -> FastAPI:
    """Create a FastAPI app including the gold desk router."""
    app = FastAPI(title="GoldDesk Test App")

    # Include the gold desk API router (prefix=/gold, tags=["GoldDesk"])
    from src.gold_desk.api import router as gold_desk_router

    app.include_router(gold_desk_router)

    return app


def test_snapshot_returns_200_with_required_fields():
    """Integration test: /gold/snapshot returns 200 with all required JSON fields."""
    app = _make_app()
    client = TestClient(app)

    response = client.get("/gold/snapshot")

    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    # The API returns {"success": True, "data": <SnapshotResponse>}
    snapshot = data.get("data") or {}
    # Verify top-level required fields exist
    assert "snapshot_at" in snapshot, "Missing 'snapshot_at' in snapshot response"
    assert "references" in snapshot, "Missing 'references' in snapshot response"
    assert "gold" in snapshot, "Missing 'gold' in snapshot response"
    assert "coins" in snapshot, "Missing 'coins' in snapshot response"
    # Verify AssetBlock fields in gold and coins (per contract: value, unit, asOf, source, quality)
    gold_assets = snapshot.get("gold", {})
    for symbol, asset in gold_assets.items():
        # Check required per-field contract
        assert "value" in asset, f"Gold {symbol} missing 'value'"
        assert "unit" in asset, f"Gold {symbol} missing 'unit'"
        assert "asOf" in asset, f"Gold {symbol} missing 'asOf'"
        assert "source" in asset, f"Gold {symbol} missing 'source'"
        assert "quality" in asset, f"Gold {symbol} missing 'quality'"
        # Verify quality is one of allowed values
        assert asset["quality"] in ("LIVE", "DELAYED", "SAMPLE", "EDUCATIONAL"), \
            f"Invalid quality value: {asset['quality']}"
        # Verify unit is one of allowed values
        assert asset["unit"] in ("toman", "rial", "ounce"), \
            f"Invalid unit value: {asset['unit']}"
        break  # Just check first gold asset
    # Also check coins
    coin_assets = snapshot.get("coins", {})
    for symbol, asset in coin_assets.items():
        assert "value" in asset, f"Coin {symbol} missing 'value'"
        assert "unit" in asset, f"Coin {symbol} missing 'unit'"
        assert "asOf" in asset, f"Coin {symbol} missing 'asOf'"
        assert "source" in asset, f"Coin {symbol} missing 'source'"
        assert "quality" in asset, f"Coin {symbol} missing 'quality'"
        assert asset["quality"] in ("LIVE", "DELAYED", "SAMPLE", "EDUCATIONAL"), \
            f"Invalid quality value: {asset['quality']}"
        assert asset["unit"] in ("toman", "rial", "ounce"), \
            f"Invalid unit value: {asset['unit']}"
        break  # Just check first coin asset


def test_snapshot_has_valid_data_structure_when_data_available():
    """Integration test: snapshot data structure is valid per schema when data available."""
    app = _make_app()
    client = TestClient(app)

    response = client.get("/gold/snapshot")

    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    snapshot = data.get("data") or {}

    # Check gold assets have required fields (may be empty if no BrsApi data)
    gold_assets = snapshot.get("gold", {})
    if gold_assets:
        first_gold_symbol = list(gold_assets.keys())[0]
        first_gold = gold_assets[first_gold_symbol]
        
        # Per contract: AssetBlock must have value, unit, asOf, source, quality
        required_fields = ["value", "unit", "asOf", "source", "quality"]
        for field in required_fields:
            assert field in first_gold, f"Gold asset missing required field: {field}"
        
        # Verify quality flag values
        assert first_gold["quality"] in ("LIVE", "DELAYED", "SAMPLE", "EDUCATIONAL")
        assert first_gold["unit"] in ("toman", "rial", "ounce")
    
    # Check coin assets have required fields (may be empty if no BrsApi data)
    coin_assets = snapshot.get("coins", {})
    if coin_assets:
        first_coin_symbol = list(coin_assets.keys())[0]
        first_coin = coin_assets[first_coin_symbol]
        
        required_fields = ["value", "unit", "asOf", "source", "quality"]
        for field in required_fields:
            assert field in first_coin, f"Coin asset missing required field: {field}"
        
        assert first_coin["quality"] in ("LIVE", "DELAYED", "SAMPLE", "EDUCATIONAL")
        assert first_coin["unit"] in ("toman", "rial", "ounce")