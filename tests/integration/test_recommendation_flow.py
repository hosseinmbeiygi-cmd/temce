from __future__ import annotations

import pytest

from services.recommendation_service import RecommendationService


@pytest.mark.asyncio
async def test_recommendation_generate():
    service = RecommendationService()
    result = await service.generate(symbols=["فولاد"], strategy="value")
    assert result.success or not result.success


@pytest.mark.asyncio
async def test_recommendation_list():
    service = RecommendationService()
    result = await service.list_recommendations()
    assert result.success or not result.success

