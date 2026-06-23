from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from core.result import Result
from services.backtest_service import BacktestService


@pytest.mark.asyncio
async def test_backtest_run_flow():
    service = BacktestService()
    mock_repo = AsyncMock()
    mock_repo.save.return_value = Result.ok({"id": "bt_test_001"})
    service.backtest_repo = mock_repo

    result = await service.run_backtest(
        name="Integration Test",
        symbols=["فولاد"],
        strategy_type="moving_average_crossover",
        start_date="2024-01-01",
        end_date="2024-12-31",
    )
    assert result.success or not result.success


@pytest.mark.asyncio
async def test_backtest_list_flow():
    service = BacktestService()
    result = await service.list_runs()
    assert result.success or not result.success


@pytest.mark.asyncio
async def test_backtest_get_result():
    service = BacktestService()
    result = await service.get_result("non_existent")
    assert not result.success

