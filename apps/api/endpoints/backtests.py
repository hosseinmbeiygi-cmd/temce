from __future__ import annotations

from fastapi import APIRouter, Depends

from apps.api.dependencies import get_backtest_service
from services.backtest_service import BacktestService

router = APIRouter()


@router.post("/run")
async def run_backtest(
    instrument_id: str = "",
    fast_period: int = 5,
    slow_period: int = 20,
    capital: float = 1_000_000_000,
    service: BacktestService = Depends(get_backtest_service),
):
    from backtesting.strategies.rule_based import MovingAverageCrossStrategy as MovingAverageCrossover

    strategy = MovingAverageCrossover(fast_period=fast_period, slow_period=slow_period, instrument_id=instrument_id)
    result = await service.run(strategy, capital=capital)
    return {"success": result.success, "data": result.value}
