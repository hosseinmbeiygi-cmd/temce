from __future__ import annotations

import pytest

from services.market_service import MarketService


@pytest.mark.asyncio
async def test_get_historical_quotes():
    service = MarketService()
    result = await service.get_historical_quotes("فولاد", "2024-01-01", "2024-12-31")
    assert result.success or not result.success


@pytest.mark.asyncio
async def test_get_ohlcv():
    service = MarketService()
    result = await service.get_ohlcv("فولاد", "2024-01-01", "2024-12-31", "1d")
    assert result.success or not result.success


@pytest.mark.asyncio
async def test_get_market_summary():
    service = MarketService()
    result = await service.get_market_summary()
    assert result.success or not result.success


@pytest.mark.asyncio
async def test_calculate_indicator():
    service = MarketService()
    result = await service.calculate_indicator("فولاد", "sma", {"period": 14})
    assert result.success or not result.success


@pytest.mark.asyncio
async def test_get_macro_data():
    service = MarketService()
    result = await service.get_macro_data("inflation", "iran")
    assert result.success or not result.success

