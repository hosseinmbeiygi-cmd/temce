from __future__ import annotations

import time
from unittest.mock import AsyncMock

import pytest

from core.result import Result
from services.quote_service import QuoteService
from tests.fixtures.sample_quotes import sample_quote


@pytest.mark.asyncio
@pytest.mark.performance
async def test_quote_bulk_ingestion():
    service = QuoteService()
    mock_repo = AsyncMock()
    mock_repo.save.return_value = Result.ok({"id": "test"})
    service.quote_repo = mock_repo

    quotes = [sample_quote(id=f"q_load_{i:04d}") for i in range(100)]
    start = time.monotonic()
    await service.save_quotes(quotes)
    elapsed = time.monotonic() - start
    throughput = 100 / elapsed
    assert throughput > 50, f"Ingestion throughput {throughput:.2f} quotes/s below 50 quotes/s threshold"
    assert True
