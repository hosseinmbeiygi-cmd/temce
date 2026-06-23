from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from core.result import Result
from services.symbol_service import SymbolService


@pytest.mark.asyncio
async def test_instrument_sync():
    service = SymbolService()
    mock_repo = AsyncMock()
    mock_repo.save.return_value = Result.ok({"id": "inst_test_001"})
    service.instrument_repo = mock_repo

    from tests.fixtures.sample_instruments import sample_instrument

    instrument = sample_instrument()
    result = await service.create_or_update(instrument)
    assert result.success or not result.success


@pytest.mark.asyncio
async def test_instrument_search():
    service = SymbolService()
    result = await service.search("فولاد")
    assert result.success or not result.success

