"""TDD tests for DomesticFXProvider (TGJU-backed).

RED: DomesticFXProvider not yet wired to TGJUClient.
GREEN: wired; all tests pass.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest


# ── helpers ───────────────────────────────────────────────────────────────────

def _mock_tgju(slugs_and_prices: dict[str, float]):
    market = {slug: {"p": str(price)} for slug, price in slugs_and_prices.items()}
    resp = MagicMock()
    resp.raise_for_status.return_value = None
    resp.json.return_value = {"market": market}
    client = MagicMock()
    client.get = AsyncMock(return_value=resp)
    client.aclose = AsyncMock()
    return client


# dollar_rl is in Rials → 580,000 Rials = 58,000 Tomans
# price_aed is in Rials → 157,000 Rials = 15,700 Tomans
_SAMPLE_PRICES = {
    "price_dollar_rl": 580_000.0,  # Rial (factor 0.1 → 58,000 Toman)
    "price_aed":       157_000.0,  # Rial (factor 0.1 → 15,700 Toman)
}


# ── 1. Import ─────────────────────────────────────────────────────────────────

def test_domestic_fx_provider_importable():
    from providers.macro.fx.domestic_fx_provider import (  # noqa: F401
        IRANIAN_CURRENCY_PAIRS,
        DomesticFXProvider,
    )


# ── 2. fetch() — happy path ───────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_fetch_returns_usd_and_aed_rates():
    from providers.macro.fx.domestic_fx_provider import DomesticFXProvider

    client = _mock_tgju(_SAMPLE_PRICES)
    result = await DomesticFXProvider(client=client).fetch()

    assert result.success
    data = result.value
    assert isinstance(data, list)
    assert len(data) == 2

    symbols = {item["symbol"] for item in data}
    assert "USD" in symbols
    assert "AED" in symbols


@pytest.mark.asyncio
async def test_fetch_converts_rial_to_toman():
    """TGJU dollar rate is in Rials; must arrive as Tomans (÷10)."""
    from providers.macro.fx.domestic_fx_provider import DomesticFXProvider

    client = _mock_tgju({"price_dollar_rl": 580_000.0})
    result = await DomesticFXProvider(client=client).fetch()

    assert result.success
    usd = next(item for item in result.value if item["symbol"] == "USD")
    assert usd["price_toman"] == pytest.approx(58_000.0)


@pytest.mark.asyncio
async def test_fetch_includes_required_fields():
    from providers.macro.fx.domestic_fx_provider import DomesticFXProvider

    client = _mock_tgju(_SAMPLE_PRICES)
    result = await DomesticFXProvider(client=client).fetch()

    item = result.value[0]
    assert "symbol" in item
    assert "slug" in item
    assert "price_toman" in item
    assert "unit" in item
    assert "fetched_at" in item


# ── 3. fetch() — pair filter ──────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_fetch_filtered_by_usd_irr():
    from providers.macro.fx.domestic_fx_provider import DomesticFXProvider

    client = _mock_tgju(_SAMPLE_PRICES)
    result = await DomesticFXProvider(client=client).fetch(pair="USD_IRR")

    assert result.success
    assert len(result.value) == 1
    assert result.value[0]["symbol"] == "USD"


@pytest.mark.asyncio
async def test_fetch_filtered_by_aed_irr():
    from providers.macro.fx.domestic_fx_provider import DomesticFXProvider

    client = _mock_tgju(_SAMPLE_PRICES)
    result = await DomesticFXProvider(client=client).fetch(pair="AED_IRR")

    assert result.success
    assert result.value[0]["symbol"] == "AED"


@pytest.mark.asyncio
async def test_fetch_case_insensitive_pair():
    from providers.macro.fx.domestic_fx_provider import DomesticFXProvider

    client = _mock_tgju(_SAMPLE_PRICES)
    result = await DomesticFXProvider(client=client).fetch(pair="usd_irr")

    assert result.success
    assert result.value[0]["symbol"] == "USD"


@pytest.mark.asyncio
async def test_fetch_unknown_pair_returns_fail():
    from providers.macro.fx.domestic_fx_provider import DomesticFXProvider

    client = _mock_tgju(_SAMPLE_PRICES)
    result = await DomesticFXProvider(client=client).fetch(pair="EUR_IRR")

    assert not result.success
    assert "EUR_IRR" in result.error


# ── 4. Error handling ─────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_fetch_returns_fail_when_tgju_unavailable():
    from providers.macro.fx.domestic_fx_provider import DomesticFXProvider

    bad = MagicMock()
    bad.get = AsyncMock(side_effect=Exception("connection refused"))
    bad.aclose = AsyncMock()

    result = await DomesticFXProvider(client=bad).fetch()
    assert not result.success


# ── 5. health() ───────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_health_returns_healthy():
    from providers.macro.fx.domestic_fx_provider import DomesticFXProvider

    client = _mock_tgju({"price_dollar_rl": 580_000.0})
    result = await DomesticFXProvider(client=client).health()

    assert result["healthy"] is True
    assert "USD" in result["message"]


@pytest.mark.asyncio
async def test_health_returns_unhealthy_on_error():
    from providers.macro.fx.domestic_fx_provider import DomesticFXProvider

    bad = MagicMock()
    bad.get = AsyncMock(side_effect=Exception("timeout"))
    bad.aclose = AsyncMock()

    result = await DomesticFXProvider(client=bad).health()
    assert result["healthy"] is False
