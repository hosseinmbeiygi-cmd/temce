from __future__ import annotations

from datetime import date

import pytest

from services.backtest_service import BacktestService


@pytest.mark.asyncio
async def test_backtest_run_flow():
    service = BacktestService()

    result = await service.run_backtest(
        name="Integration Test",
        symbols=["فولاد"],
        strategy_type="moving_average_cross",
        start_date=date(2024, 1, 1),
        end_date=date(2024, 12, 31),
    )
    assert result.success


@pytest.mark.asyncio
async def test_backtest_list_flow():
    service = BacktestService()
    result = await service.list_runs()
    assert result.success


@pytest.mark.asyncio
async def test_backtest_get_result():
    service = BacktestService()
    result = await service.get_result("non_existent")
    assert result.success is True
    assert result.value is None

