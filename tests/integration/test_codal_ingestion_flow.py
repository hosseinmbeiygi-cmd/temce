from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from core.result import Result
from services.codal_service import CodalService


@pytest.mark.asyncio
async def test_codal_fetch_and_store():
    service = CodalService()
    mock_repo = AsyncMock()
    mock_repo.save.return_value = Result.ok({"id": "cod_test_001"})
    service.repo = mock_repo

    result = await service.create(instrument_id="فولاد", title="Test Disclosure")
    assert result.success


@pytest.mark.asyncio
async def test_codal_search():
    service = CodalService()
    result = await service.list_all(page=1, page_size=50)
    assert result.success
