from __future__ import annotations

import time
from unittest.mock import AsyncMock

import pytest

from core.result import Result
from services.backtest_service import BacktestService


@pytest.mark.asyncio
@pytest.mark.performance
async def test_backtest_batch_execution():
    service = BacktestService()
    mock_repo = AsyncMock()
    mock_repo.save.return_value = Result.ok({"id": "test"})
    service.backtest_repo = mock_repo

    start = time.monotonic()
    results = []
    for i in range(20):
        result = await service.run_backtest(
            name=f"Load Test {i}",
            symbols=["فولاد"],
            strategy_type="moving_average_crossover",
            start_date="2024-01-01",
            end_date="2024-12-31",
        )
        results.append(result)
    elapsed = time.monotonic() - start
    avg = elapsed / 20
    assert avg < 2.0, f"Average backtest execution {avg:.2f}s exceeds 2s threshold"
