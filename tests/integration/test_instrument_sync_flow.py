from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from core.result import Result
from services.symbol_service import SymbolService


@pytest.mark.asyncio
async def test_instrument_sync():
    service = SymbolService()
    mock_repo = AsyncMock()

    async def _fake_save(inst):
        return Result.ok(inst)

    mock_repo.save.side_effect = _fake_save
    service.repo = mock_repo

    result = await service.create(symbol="فولاد", name="فولاد مبارکه اصفهان", isin="IRO1FOLD0001")
    assert result.success


@pytest.mark.asyncio
async def test_instrument_search():
    service = SymbolService()
    result = await service.search("فولاد")
    assert result.success

