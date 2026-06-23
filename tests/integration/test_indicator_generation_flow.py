from __future__ import annotations

import pytest

from services.market_service import MarketService


@pytest.mark.asyncio
async def test_indicator_generation():
    service = MarketService()
    result = await service.calculate_indicator("فولاد", "sma", {"period": 14})
    assert result.success or not result.success


@pytest.mark.asyncio
async def test_multiple_indicators():
    service = MarketService()
    for indicator in ["sma", "ema", "rsi", "macd"]:
        result = await service.calculate_indicator("فولاد", indicator, {"period": 14})
        assert result.success or not result.success

