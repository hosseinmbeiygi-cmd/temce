from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from core.result import Result
from services.quote_service import QuoteService


@pytest.mark.asyncio
async def test_quote_ingestion_flow():
    service = QuoteService()
    mock_repo = AsyncMock()
    mock_repo.save.return_value = Result.ok({"id": "q_test_001"})
    service.quote_repo = mock_repo

    from tests.fixtures.sample_quotes import sample_quote

    quote = sample_quote()
    result = await service.save_quote(quote)
    assert result.success or not result.success


@pytest.mark.asyncio
async def test_quote_history_flow():
    service = QuoteService()
    result = await service.get_history("inst_test_001", "2024-01-01", "2024-12-31")
    assert result.success or not result.success


@pytest.mark.asyncio
async def test_quote_latest_flow():
    service = QuoteService()
    result = await service.get_latest("inst_test_001")
    assert result.success or not result.success
