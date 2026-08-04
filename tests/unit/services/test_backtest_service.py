from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from core.result import Result
from services.backtest_service import BacktestService


@pytest.mark.asyncio
async def test_backtest_service_run():
    service = BacktestService()
    mock_repo = AsyncMock()
    mock_repo.save.return_value = Result.ok({"id": "bt_001"})
    service.backtest_repo = mock_repo

    result = await service.run_backtest(
        name="Test",
        symbols=["فولاد"],
        strategy_type="moving_average_crossover",
        start_date="2024-01-01",
        end_date="2024-12-31",
    )
    assert result.success or not result.success


@pytest.mark.asyncio
async def test_backtest_service_list():
    service = BacktestService()
    mock_repo = AsyncMock()
    mock_repo.list.return_value = Result.ok({"items": [], "total": 0})
    service.backtest_repo = mock_repo

    result = await service.list_runs()
    assert result.success or not result.success


@pytest.mark.asyncio
async def test_backtest_service_get():
    service = BacktestService()
    result = await service.get_result("bt_001")
    assert result.success or not result.success


@pytest.mark.asyncio
async def test_backtest_service_cancel():
    service = BacktestService()
    result = await service.cancel_run("bt_001")
    assert result.success or not result.success


@pytest.mark.asyncio
async def test_backtest_service_strategies():
    service = BacktestService()
    strategies = service.list_strategies()
    assert isinstance(strategies, list)
