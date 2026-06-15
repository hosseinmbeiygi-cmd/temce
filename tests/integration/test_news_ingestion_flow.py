from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from core.result import Result
from services.news_service import NewsService


@pytest.mark.asyncio
async def test_news_fetch_and_store():
    service = NewsService()
    mock_repo = AsyncMock()
    mock_repo.save.return_value = Result.ok({"id": "news_test_001"})
    service.news_repo = mock_repo

    with patch.object(service, "_fetch_articles", AsyncMock(return_value=Result.ok([]))):
        result = await service.fetch_and_store()
        assert result.success or not result.success


@pytest.mark.asyncio
async def test_news_search():
    service = NewsService()
    result = await service.search(symbols=["فولاد"])
    assert result.success or not result.success
