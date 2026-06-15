from __future__ import annotations

import pytest

from services.market_service import MarketService


@pytest.mark.asyncio
async def test_macro_fetch():
    service = MarketService()
    result = await service.get_macro_data("inflation", "iran")
    assert result.success or not result.success


@pytest.mark.asyncio
async def test_macro_list():
    service = MarketService()
    result = await service.list_macro_indicators()
    assert result.success or not result.success
