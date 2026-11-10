"""TDD tests for GlobalGoldProvider (goldapi.io + OKX PAXG + Yahoo Finance GC=F).

RED: GlobalGoldProvider not yet implemented.
GREEN: wired; all tests pass.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest


# ── helpers ───────────────────────────────────────────────────────────────────

def _mock_goldapi_response(price: float) -> MagicMock:
    resp = MagicMock()
    resp.raise_for_status.return_value = None
    resp.json.return_value = {"price": price, "currency": "USD"}
    client = MagicMock()
    client.get = AsyncMock(return_value=resp)
    client.aclose = AsyncMock()
    return client


def _mock_yahoo_response(price: float) -> MagicMock:
    resp = MagicMock()
    resp.raise_for_status.return_value = None
    resp.json.return_value = {
        "chart": {
            "result": [{"meta": {"regularMarketPrice": price}}]
        }
    }
    client = MagicMock()
    client.get = AsyncMock(return_value=resp)
    client.aclose = AsyncMock()
    return client


def _mock_okx_response(price: float) -> MagicMock:
    resp = MagicMock()
    resp.raise_for_status.return_value = None
    resp.json.return_value = {"data": [{"last": str(price)}]}
    client = MagicMock()
    client.get = AsyncMock(return_value=resp)
    client.aclose = AsyncMock()
    return client


# ── 1. Import ─────────────────────────────────────────────────────────────────

def test_global_gold_provider_importable():
    from providers.macro.gold.global_gold_provider import (  # noqa: F401
        GLOBAL_GOLD_BENCHMARKS,
        GlobalGoldProvider,
    )


def test_global_gold_benchmarks_contains_xau():
    from providers.macro.gold.global_gold_provider import GLOBAL_GOLD_BENCHMARKS

    assert "XAU_USD" in GLOBAL_GOLD_BENCHMARKS
    assert "XAG_USD" in GLOBAL_GOLD_BENCHMARKS
    assert "XPT_USD" in GLOBAL_GOLD_BENCHMARKS


# ── 2. fetch() with goldapi.io key ────────────────────────────────────────────

@pytest.mark.asyncio
async def test_fetch_xau_usd_via_goldapi():
    from providers.macro.gold.global_gold_provider import GlobalGoldProvider

    http_client = _mock_goldapi_response(2683.5)
    with patch("providers.macro.gold.global_gold_provider.get_goldapi_key", return_value="test-key"):
        with patch("providers.macro.gold.global_gold_provider.fetch_xau_usd", new_callable=AsyncMock, return_value=2683.5):
            with patch("providers.macro.gold.global_gold_provider._fetch_xag_goldapi", new_callable=AsyncMock, return_value=31.5):
                with patch("providers.macro.gold.global_gold_provider._fetch_xpt_goldapi", new_callable=AsyncMock, return_value=950.0):
                    provider = GlobalGoldProvider(http_client=http_client)
                    result = await provider.fetch()

    assert result.success
    data = result.value
    benchmarks = {item["benchmark"] for item in data}
    assert "XAU_USD" in benchmarks


@pytest.mark.asyncio
async def test_fetch_xau_fallback_to_paxg_when_no_key():
    from providers.macro.gold.global_gold_provider import GlobalGoldProvider

    with patch("providers.macro.gold.global_gold_provider.get_goldapi_key", return_value=None):
        with patch("providers.macro.gold.global_gold_provider.fetch_paxg_binance", new_callable=AsyncMock, return_value=2680.0):
            result = await GlobalGoldProvider().fetch()

    assert result.success
    xau = next(item for item in result.value if item["benchmark"] == "XAU_USD")
    assert xau["price_usd"] == pytest.approx(2680.0)


@pytest.mark.asyncio
async def test_fetch_xau_fallback_to_yahoo_when_paxg_fails():
    from providers.macro.gold.global_gold_provider import GlobalGoldProvider

    http_client = _mock_yahoo_response(2675.0)
    with patch("providers.macro.gold.global_gold_provider.get_goldapi_key", return_value=None):
        with patch("providers.macro.gold.global_gold_provider.fetch_paxg_binance", new_callable=AsyncMock, return_value=None):
            provider = GlobalGoldProvider(http_client=http_client)
            result = await provider.fetch()

    assert result.success
    xau = next(item for item in result.value if item["benchmark"] == "XAU_USD")
    assert xau["price_usd"] == pytest.approx(2675.0)


@pytest.mark.asyncio
async def test_fetch_returns_fail_when_all_sources_unavailable():
    from providers.macro.gold.global_gold_provider import GlobalGoldProvider

    bad = MagicMock()
    bad.get = AsyncMock(side_effect=Exception("network error"))
    bad.aclose = AsyncMock()

    with patch("providers.macro.gold.global_gold_provider.get_goldapi_key", return_value=None):
        with patch("providers.macro.gold.global_gold_provider.fetch_paxg_binance", new_callable=AsyncMock, return_value=None):
            result = await GlobalGoldProvider(http_client=bad).fetch()

    assert not result.success
    assert "unavailable" in result.error.lower()


# ── 3. fetch() — benchmark filter ────────────────────────────────────────────

@pytest.mark.asyncio
async def test_fetch_benchmark_xau_only():
    from providers.macro.gold.global_gold_provider import GlobalGoldProvider

    with patch("providers.macro.gold.global_gold_provider.get_goldapi_key", return_value=None):
        with patch("providers.macro.gold.global_gold_provider.fetch_paxg_binance", new_callable=AsyncMock, return_value=2680.0):
            result = await GlobalGoldProvider().fetch(benchmark="XAU_USD")

    assert result.success
    assert len(result.value) == 1
    assert result.value[0]["benchmark"] == "XAU_USD"


# ── 4. health() ───────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_health_returns_healthy():
    from providers.macro.gold.global_gold_provider import GlobalGoldProvider

    with patch("providers.macro.gold.global_gold_provider.get_goldapi_key", return_value=None):
        with patch("providers.macro.gold.global_gold_provider.fetch_paxg_binance", new_callable=AsyncMock, return_value=2680.0):
            result = await GlobalGoldProvider().health()

    assert result["healthy"] is True
    assert "XAU/USD" in result["message"] or "2680" in result["message"]


@pytest.mark.asyncio
async def test_health_returns_unhealthy_when_no_sources():
    from providers.macro.gold.global_gold_provider import GlobalGoldProvider

    bad = MagicMock()
    bad.get = AsyncMock(side_effect=Exception("timeout"))
    bad.aclose = AsyncMock()

    with patch("providers.macro.gold.global_gold_provider.get_goldapi_key", return_value=None):
        with patch("providers.macro.gold.global_gold_provider.fetch_paxg_binance", new_callable=AsyncMock, return_value=None):
            result = await GlobalGoldProvider(http_client=bad).health()

    assert result["healthy"] is False
