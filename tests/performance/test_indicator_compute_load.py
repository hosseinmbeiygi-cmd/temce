from __future__ import annotations

import time

import pytest

from services.market_service import MarketService


@pytest.mark.asyncio
@pytest.mark.performance
async def test_indicator_bulk_computation():
    service = MarketService()
    symbols = ["فولاد", "فملی", "وبانک", "کگل", "خودرو", "شستا", "حافظ", "آریا", "دماوند", "سینا"]
    indicator_types = ["sma", "ema", "rsi", "macd", "bbands"]

    start = time.monotonic()
    count = 0
    for symbol in symbols:
        for ind_type in indicator_types:
            await service.calculate_indicator(symbol, ind_type, {"period": 14})
            count += 1
    elapsed = time.monotonic() - start
    avg = elapsed / count
    assert avg < 1.0, f"Average indicator computation {avg:.2f}s exceeds 1s threshold"
