from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from core.result import Result
from services.news_service import NewsService


@pytest.mark.asyncio
async def test_news_fetch_and_store():
    service = NewsService()
    mock_repo = AsyncMock()
    mock_repo.save.return_value = Result.ok({"id": "news_test_001"})
    service.repo = mock_repo

    result = await service.create(title="Test Article", symbols=["فولاد"], content="Test")
    assert result.success


@pytest.mark.asyncio
async def test_news_search():
    service = NewsService()
    result = await service.search(query="فولاد")
    assert result.success

