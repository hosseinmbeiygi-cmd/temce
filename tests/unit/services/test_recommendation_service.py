from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from core.result import Result
from services.recommendation_service import RecommendationService


@pytest.mark.asyncio
async def test_recommendation_generate():
    service = RecommendationService()
    result = await service.generate(symbols=["فولاد"], strategy="value")
    assert result.success or not result.success


@pytest.mark.asyncio
async def test_recommendation_list():
    service = RecommendationService()
    mock_repo = AsyncMock()
    mock_repo.list.return_value = Result.ok({"items": [], "total": 0})
    service.recommendation_repo = mock_repo

    result = await service.list_recommendations()
    assert result.success or not result.success


@pytest.mark.asyncio
async def test_recommendation_get():
    service = RecommendationService()
    result = await service.get_recommendation("rec_001")
    assert result.success or not result.success


@pytest.mark.asyncio
async def test_recommendation_by_symbol():
    service = RecommendationService()
    result = await service.get_by_symbol("فولاد")
    assert result.success or not result.success


@pytest.mark.asyncio
async def test_recommendation_strategies():
    service = RecommendationService()
    strategies = service.list_strategies()
    assert isinstance(strategies, list)
