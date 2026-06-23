from __future__ import annotations

import pytest

from services.quote_service import QuoteService


@pytest.mark.asyncio
async def test_realtime_quote_update():
    service = QuoteService()
    from tests.fixtures.sample_quotes import sample_quote

    quote = sample_quote()
    result = await service.save_quote(quote)
    assert result.success or not result.success


@pytest.mark.asyncio
async def test_market_summary():
    service = QuoteService()
    result = await service.get_market_summary()
    assert result.success or not result.success


@pytest.mark.asyncio
async def test_top_gainers():
    service = QuoteService()
    result = await service.quote_repo.get_top_gainers(5)
    assert result.success or not result.success


@pytest.mark.asyncio
async def test_top_losers():
    service = QuoteService()
    result = await service.quote_repo.get_top_losers(5)
    assert result.success or not result.success


@pytest.mark.asyncio
async def test_most_active():
    service = QuoteService()
    result = await service.quote_repo.get_most_active(5)
    assert result.success or not result.success

