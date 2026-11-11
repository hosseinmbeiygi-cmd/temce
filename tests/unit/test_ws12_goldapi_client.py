"""WS12: International XAU/USD client — goldapi.io + Binance PAXG (TDD).

RED (before implementation):
  1. goldapi_client module does not exist.
  2. fetch_xau_usd / fetch_paxg_binance / get_international_xau_usd not importable.

GREEN (after implementation):
  1. fetch_xau_usd(key, mock_client) returns float on valid 200 response.
  2. fetch_xau_usd returns None on network error.
  3. fetch_xau_usd returns None on non-200 HTTP status.
  4. fetch_xau_usd returns None when price=0 or negative.
  5. fetch_xau_usd returns None when price key missing.
  6. get_goldapi_key() returns env var or None.
  7. get_goldapi_xau_usd() returns None when key not set (no network call).
"""
from __future__ import annotations

import os
import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


# ─── 1. Import check ─────────────────────────────────────────────────────────

def test_import_goldapi_client():
    """goldapi_client must be importable from src.gold_desk.

    RED: module does not exist.
    GREEN: module created with all public functions.
    """
    from src.gold_desk.goldapi_client import (  # noqa: F401
        fetch_paxg_binance,
        fetch_xau_usd,
        get_goldapi_key,
        get_goldapi_xau_usd,
        get_international_xau_usd,
    )


# ─── helpers ─────────────────────────────────────────────────────────────────

def _mock_client(status_code: int = 200, json_data: dict | None = None) -> MagicMock:
    resp = MagicMock()
    resp.status_code = status_code
    resp.json.return_value = json_data or {"price": 2683.45, "metal": "XAU", "currency": "USD"}
    if status_code >= 400:
        resp.raise_for_status.side_effect = Exception(f"HTTP {status_code}")
    else:
        resp.raise_for_status.return_value = None
    client = MagicMock()
    client.get = AsyncMock(return_value=resp)
    client.aclose = AsyncMock()
    return client


# ─── 2. Happy path ───────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_fetch_xau_usd_returns_float_on_success():
    """fetch_xau_usd returns float when API responds with valid price.

    RED: module missing.
    GREEN: parses 'price' field from JSON.
    """
    from src.gold_desk.goldapi_client import fetch_xau_usd

    client = _mock_client(200, {"price": 2683.45})
    result = await fetch_xau_usd("test-key", client=client)
    assert result == pytest.approx(2683.45)
    client.get.assert_awaited_once()


@pytest.mark.asyncio
async def test_fetch_xau_usd_passes_key_in_header():
    """x-access-token header must contain the API key.

    RED: not tested.
    GREEN: header set in httpx.get() call.
    """
    from src.gold_desk.goldapi_client import fetch_xau_usd

    client = _mock_client(200, {"price": 2500.0})
    await fetch_xau_usd("my-secret-key", client=client)
    _call_kwargs = client.get.call_args
    headers = _call_kwargs.kwargs.get("headers", {}) or (_call_kwargs.args[1] if len(_call_kwargs.args) > 1 else {})
    assert headers.get("x-access-token") == "my-secret-key"


# ─── 3. Error cases ──────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_fetch_xau_usd_returns_none_on_http_error():
    """fetch_xau_usd returns None on 4xx/5xx responses.

    RED: not tested.
    GREEN: exception caught, returns None.
    """
    from src.gold_desk.goldapi_client import fetch_xau_usd

    client = _mock_client(401)
    result = await fetch_xau_usd("bad-key", client=client)
    assert result is None


@pytest.mark.asyncio
async def test_fetch_xau_usd_returns_none_on_network_error():
    """fetch_xau_usd returns None when httpx raises (timeout, DNS etc.).

    RED: not tested.
    GREEN: exception caught in try/except.
    """
    from src.gold_desk.goldapi_client import fetch_xau_usd

    client = MagicMock()
    client.get = AsyncMock(side_effect=Exception("connection refused"))
    client.aclose = AsyncMock()
    result = await fetch_xau_usd("test-key", client=client)
    assert result is None


@pytest.mark.asyncio
async def test_fetch_xau_usd_returns_none_when_price_zero():
    """fetch_xau_usd returns None when price is 0 (invalid market data).

    RED: not tested.
    GREEN: guard `price <= 0` returns None.
    """
    from src.gold_desk.goldapi_client import fetch_xau_usd

    client = _mock_client(200, {"price": 0})
    result = await fetch_xau_usd("test-key", client=client)
    assert result is None


@pytest.mark.asyncio
async def test_fetch_xau_usd_returns_none_when_price_negative():
    """fetch_xau_usd returns None when price is negative.

    RED: not tested.
    GREEN: same guard `price <= 0`.
    """
    from src.gold_desk.goldapi_client import fetch_xau_usd

    client = _mock_client(200, {"price": -100.0})
    result = await fetch_xau_usd("test-key", client=client)
    assert result is None


@pytest.mark.asyncio
async def test_fetch_xau_usd_returns_none_when_price_missing():
    """fetch_xau_usd returns None when 'price' key absent in response.

    RED: not tested.
    GREEN: data.get('price') returns None → guard triggers.
    """
    from src.gold_desk.goldapi_client import fetch_xau_usd

    client = _mock_client(200, {"metal": "XAU", "currency": "USD"})
    result = await fetch_xau_usd("test-key", client=client)
    assert result is None


# ─── 4. get_goldapi_key ───────────────────────────────────────────────────────

def test_get_goldapi_key_returns_env_value():
    """get_goldapi_key() returns GOLDAPI_KEY env var when set.

    RED: module missing.
    GREEN: os.getenv('GOLDAPI_KEY').
    """
    from src.gold_desk.goldapi_client import get_goldapi_key

    with patch.dict(os.environ, {"GOLDAPI_KEY": "test-api-key-123"}):
        assert get_goldapi_key() == "test-api-key-123"


def test_get_goldapi_key_returns_none_when_not_set():
    """get_goldapi_key() returns None when GOLDAPI_KEY is absent.

    RED: module missing.
    GREEN: os.getenv returns None.
    """
    from src.gold_desk.goldapi_client import get_goldapi_key

    env = {k: v for k, v in os.environ.items() if k != "GOLDAPI_KEY"}
    with patch.dict(os.environ, env, clear=True):
        assert get_goldapi_key() is None


# ─── 5. get_goldapi_xau_usd (no-key guard) ───────────────────────────────────

@pytest.mark.asyncio
async def test_get_goldapi_xau_usd_returns_none_when_key_absent():
    """get_goldapi_xau_usd() returns None without making any network call.

    RED: not tested.
    GREEN: get_goldapi_key() == None → returns None immediately.
    """
    from src.gold_desk.goldapi_client import get_goldapi_xau_usd

    env = {k: v for k, v in os.environ.items() if k != "GOLDAPI_KEY"}
    with patch.dict(os.environ, env, clear=True):
        result = await get_goldapi_xau_usd()
    assert result is None


# ─── 6. fetch_paxg_binance ────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_fetch_paxg_binance_returns_float_on_success():
    """fetch_paxg_binance returns float from OKX PAXG/USDT.

    RED: not tested.
    GREEN: parses 'last' from OKX ticker response (data[0].last).
    Note: uses OKX (not Binance) — Binance returns HTTP 451 from Iran.
    """
    from src.gold_desk.goldapi_client import fetch_paxg_binance

    resp = MagicMock()
    resp.raise_for_status.return_value = None
    resp.json.return_value = {"data": [{"instId": "PAXG-USDT", "last": "2683.5"}]}
    client = MagicMock()
    client.get = AsyncMock(return_value=resp)
    client.aclose = AsyncMock()

    result = await fetch_paxg_binance(client=client)
    assert result == pytest.approx(2683.5)


@pytest.mark.asyncio
async def test_fetch_paxg_binance_returns_none_on_error():
    """fetch_paxg_binance returns None on network error.

    RED: not tested.
    GREEN: exception caught, returns None.
    """
    from src.gold_desk.goldapi_client import fetch_paxg_binance

    client = MagicMock()
    client.get = AsyncMock(side_effect=Exception("timeout"))
    client.aclose = AsyncMock()

    result = await fetch_paxg_binance(client=client)
    assert result is None


@pytest.mark.asyncio
async def test_fetch_paxg_binance_returns_none_on_zero_price():
    """fetch_paxg_binance returns None when last price is '0'.

    RED: not tested.
    GREEN: float('0') <= 0 → returns None.
    """
    from src.gold_desk.goldapi_client import fetch_paxg_binance

    resp = MagicMock()
    resp.raise_for_status.return_value = None
    resp.json.return_value = {"data": [{"instId": "PAXG-USDT", "last": "0"}]}
    client = MagicMock()
    client.get = AsyncMock(return_value=resp)
    client.aclose = AsyncMock()

    result = await fetch_paxg_binance(client=client)
    assert result is None


@pytest.mark.asyncio
async def test_fetch_paxg_binance_returns_none_on_empty_data():
    """fetch_paxg_binance returns None when OKX data array is empty.

    RED: not tested.
    GREEN: guard `if not items` returns None.
    """
    from src.gold_desk.goldapi_client import fetch_paxg_binance

    resp = MagicMock()
    resp.raise_for_status.return_value = None
    resp.json.return_value = {"data": []}
    client = MagicMock()
    client.get = AsyncMock(return_value=resp)
    client.aclose = AsyncMock()

    result = await fetch_paxg_binance(client=client)
    assert result is None


# ─── 7. get_international_xau_usd (priority logic) ───────────────────────────

@pytest.mark.asyncio
async def test_get_international_uses_goldapi_when_key_set():
    """get_international_xau_usd prefers goldapi.io when GOLDAPI_KEY is set.

    RED: function missing.
    GREEN: goldapi.io called first; Binance not called if goldapi succeeds.
    """
    from src.gold_desk import goldapi_client

    env = {**os.environ, "GOLDAPI_KEY": "test-key"}
    with patch.dict(os.environ, env):
        with patch.object(goldapi_client, "fetch_xau_usd", new=AsyncMock(return_value=2700.0)) as mock_gold, \
             patch.object(goldapi_client, "fetch_paxg_binance", new=AsyncMock(return_value=2690.0)) as mock_paxg:
            result = await goldapi_client.get_international_xau_usd()

    assert result == pytest.approx(2700.0)
    mock_gold.assert_awaited_once()
    mock_paxg.assert_not_awaited()


@pytest.mark.asyncio
async def test_get_international_falls_back_to_paxg_when_goldapi_fails():
    """get_international_xau_usd falls back to PAXG when goldapi.io returns None.

    RED: not tested.
    GREEN: goldapi returns None → Binance PAXG called.
    """
    from src.gold_desk import goldapi_client

    env = {**os.environ, "GOLDAPI_KEY": "test-key"}
    with patch.dict(os.environ, env):
        with patch.object(goldapi_client, "fetch_xau_usd", new=AsyncMock(return_value=None)), \
             patch.object(goldapi_client, "fetch_paxg_binance", new=AsyncMock(return_value=2680.0)) as mock_paxg:
            result = await goldapi_client.get_international_xau_usd()

    assert result == pytest.approx(2680.0)
    mock_paxg.assert_awaited_once()


@pytest.mark.asyncio
async def test_get_international_uses_paxg_when_no_key():
    """get_international_xau_usd uses PAXG directly when no GOLDAPI_KEY.

    RED: not tested.
    GREEN: key is None → skip goldapi, call Binance PAXG.
    """
    from src.gold_desk import goldapi_client

    env = {k: v for k, v in os.environ.items() if k != "GOLDAPI_KEY"}
    with patch.dict(os.environ, env, clear=True):
        with patch.object(goldapi_client, "fetch_paxg_binance", new=AsyncMock(return_value=2675.0)) as mock_paxg:
            result = await goldapi_client.get_international_xau_usd()

    assert result == pytest.approx(2675.0)
    mock_paxg.assert_awaited_once()
