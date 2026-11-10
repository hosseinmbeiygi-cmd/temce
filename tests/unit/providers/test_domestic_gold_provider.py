"""TDD tests for DomesticGoldProvider (TGJU-backed).

RED: DomesticGoldProvider not yet wired to TGJUClient.
GREEN: wired; all tests pass.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from providers.macro_sources.tgju import TGJU_PRICE_MAP, TGJUQuote

# ── helpers ───────────────────────────────────────────────────────────────────

def _mock_tgju(slugs_and_prices: dict[str, float]):
    """Return a mock httpx client that makes TGJUClient return specific prices."""
    market = {
        slug: {"p": str(price)}
        for slug, price in slugs_and_prices.items()
    }
    resp = MagicMock()
    resp.raise_for_status.return_value = None
    resp.json.return_value = {"market": market}
    client = MagicMock()
    client.get = AsyncMock(return_value=resp)
    client.aclose = AsyncMock()
    return client


_SAMPLE_PRICES = {
    "geram18":    17_500_000.0,
    "geram24":    19_000_000.0,
    "coin-emami": 75_000_000.0,
    "coin-bahar": 72_000_000.0,
    "coin-half":  38_000_000.0,
    "coin-quarter": 20_000_000.0,
}


# ── 1. Import ─────────────────────────────────────────────────────────────────

def test_domestic_gold_provider_importable():
    from providers.macro.gold.domestic_gold_provider import (  # noqa: F401
        IRANIAN_GOLD_TYPES,
        DomesticGoldProvider,
    )


# ── 2. fetch() — happy path ───────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_fetch_returns_all_gold_prices():
    from providers.macro.gold.domestic_gold_provider import DomesticGoldProvider

    client = _mock_tgju(_SAMPLE_PRICES)
    provider = DomesticGoldProvider(client=client)
    result = await provider.fetch()

    assert result.success
    data = result.value
    assert isinstance(data, list)
    assert len(data) == 6

    symbols = {item["symbol"] for item in data}
    assert "IR_GOLD_18K_GRAM" in symbols
    assert "IR_COIN_EMAMI" in symbols
    assert "IR_COIN_BAHAR" in symbols


@pytest.mark.asyncio
async def test_fetch_returns_correct_prices():
    from providers.macro.gold.domestic_gold_provider import DomesticGoldProvider

    client = _mock_tgju(_SAMPLE_PRICES)
    provider = DomesticGoldProvider(client=client)
    result = await provider.fetch()

    by_symbol = {item["symbol"]: item for item in result.value}
    assert by_symbol["IR_GOLD_18K_GRAM"]["price"] == pytest.approx(17_500_000.0)
    assert by_symbol["IR_COIN_EMAMI"]["price"] == pytest.approx(75_000_000.0)


@pytest.mark.asyncio
async def test_fetch_includes_required_fields():
    from providers.macro.gold.domestic_gold_provider import DomesticGoldProvider

    client = _mock_tgju(_SAMPLE_PRICES)
    result = await DomesticGoldProvider(client=client).fetch()

    item = result.value[0]
    assert "symbol" in item
    assert "slug" in item
    assert "price" in item
    assert "unit" in item
    assert "fetched_at" in item


# ── 3. fetch() — gold_type filter ────────────────────────────────────────────

@pytest.mark.asyncio
async def test_fetch_filtered_by_gold_type_bahar_azadi():
    from providers.macro.gold.domestic_gold_provider import DomesticGoldProvider

    client = _mock_tgju(_SAMPLE_PRICES)
    result = await DomesticGoldProvider(client=client).fetch(gold_type="bahar_azadi")

    assert result.success
    assert len(result.value) == 1
    assert result.value[0]["symbol"] == "IR_COIN_BAHAR"


@pytest.mark.asyncio
async def test_fetch_filtered_by_gold_type_nim_azadi():
    from providers.macro.gold.domestic_gold_provider import DomesticGoldProvider

    client = _mock_tgju(_SAMPLE_PRICES)
    result = await DomesticGoldProvider(client=client).fetch(gold_type="nim_azadi")

    assert result.success
    assert result.value[0]["symbol"] == "IR_COIN_HALF"


@pytest.mark.asyncio
async def test_fetch_unknown_gold_type_returns_fail():
    from providers.macro.gold.domestic_gold_provider import DomesticGoldProvider

    client = _mock_tgju(_SAMPLE_PRICES)
    result = await DomesticGoldProvider(client=client).fetch(gold_type="unknown_type")

    assert not result.success
    assert "Unknown gold_type" in result.error


# ── 4. Error handling ─────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_fetch_returns_fail_when_tgju_unavailable():
    from providers.macro.gold.domestic_gold_provider import DomesticGoldProvider

    bad = MagicMock()
    bad.get = AsyncMock(side_effect=Exception("network error"))
    bad.aclose = AsyncMock()

    result = await DomesticGoldProvider(client=bad).fetch()
    assert not result.success


# ── 5. health() ───────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_health_returns_healthy_when_prices_available():
    from providers.macro.gold.domestic_gold_provider import DomesticGoldProvider

    client = _mock_tgju({"geram18": 17_500_000.0})
    result = await DomesticGoldProvider(client=client).health()

    assert result["healthy"] is True
    assert "17500000" in result["message"] or "geram18" in result["message"]


@pytest.mark.asyncio
async def test_health_returns_unhealthy_on_network_error():
    from providers.macro.gold.domestic_gold_provider import DomesticGoldProvider

    bad = MagicMock()
    bad.get = AsyncMock(side_effect=Exception("timeout"))
    bad.aclose = AsyncMock()

    result = await DomesticGoldProvider(client=bad).health()
    assert result["healthy"] is False


# ── 6. IRANIAN_GOLD_TYPES constant ───────────────────────────────────────────

def test_iranian_gold_types_contains_expected_types():
    from providers.macro.gold.domestic_gold_provider import IRANIAN_GOLD_TYPES

    assert "bahar_azadi" in IRANIAN_GOLD_TYPES
    assert "nim_azadi" in IRANIAN_GOLD_TYPES
