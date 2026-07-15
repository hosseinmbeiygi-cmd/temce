from __future__ import annotations

import pytest

from services.macro_service import MacroService
from services.market_service import MarketService


@pytest.mark.asyncio
async def test_macro_fetch():
    service = MarketService()
    result = await service.get_macro_data("inflation", "iran")
    assert result.success


@pytest.mark.asyncio
async def test_macro_list():
    service = MacroService()
    result = await service.list_indicators()
    assert result.success

