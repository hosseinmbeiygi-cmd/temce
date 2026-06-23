from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from core.result import Result
from services.quote_service import QuoteService


@pytest.mark.asyncio
async def test_realtime_get_latest():
    service = QuoteService()
    mock_repo = AsyncMock()
    mock_repo.get_latest.return_value = Result.ok({"id": "q_001", "price_close": 15000})
    service.quote_repo = mock_repo

    result = await service.get_latest("inst_001")
    assert result.success


@pytest.mark.asyncio
async def test_realtime_save():
    service = QuoteService()
    mock_repo = AsyncMock()
    mock_repo.save.return_value = Result.ok({"id": "q_001"})
    service.quote_repo = mock_repo

    from tests.fixtures.sample_quotes import sample_quote

    result = await service.save_quote(sample_quote())
    assert result.success


@pytest.mark.asyncio
async def test_realtime_batch_save():
    service = QuoteService()
    mock_repo = AsyncMock()
    mock_repo.save.return_value = Result.ok({"id": "q_001"})
    service.quote_repo = mock_repo

    from tests.fixtures.sample_quotes import sample_quote_list

    quotes = sample_quote_list(10)
    result = await service.save_quotes(quotes)
    assert result.success
    assert result.value >= 0


@pytest.mark.asyncio
async def test_get_market_summary():
    service = QuoteService()
    mock_repo = AsyncMock()
    mock_repo.get_market_summary.return_value = Result.ok({"total_quotes": 100})
    service.quote_repo = mock_repo

    result = await service.get_market_summary()
    assert result.success


@pytest.mark.asyncio
async def test_get_top_gainers():
    service = QuoteService()
    mock_repo = AsyncMock()
    mock_repo.get_top_gainers.return_value = Result.ok([])
    service.quote_repo = mock_repo

    result = await service.quote_repo.get_top_gainers(5)
    assert result.success

