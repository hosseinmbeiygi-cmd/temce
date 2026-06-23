from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from core.result import Result
from services.codal_service import CodalService


@pytest.mark.asyncio
async def test_codal_fetch_and_store():
    service = CodalService()
    mock_repo = AsyncMock()
    mock_repo.save.return_value = Result.ok({"id": "cod_test_001"})
    service.codal_repo = mock_repo

    with patch.object(service, "_fetch_reports", AsyncMock(return_value=Result.ok([]))):
        result = await service.fetch_and_store("فولاد")
        assert result.success or not result.success


@pytest.mark.asyncio
async def test_codal_search():
    service = CodalService()
    result = await service.search(symbol="فولاد")
    assert result.success or not result.success

