#!/usr/bin/env python
from __future__ import annotations

# --- auto PYTHONPATH ---
import sys
from pathlib import Path
_project_root = Path(__file__).resolve().parent.parent
if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))
# --- end auto PYTHONPATH ---

import asyncio

from core.logging import get_logger
from services.backtest_service import BacktestService

logger = get_logger(__name__)


async def main() -> None:
    service = BacktestService()
    result = await service.run_backtest(
        name="Sample SMA Crossover",
        symbols=["فولاد"],
        strategy_type="moving_average_crossover",
        strategy_params={"fast_period": 20, "slow_period": 50},
        start_date="2024-01-01",
        end_date="2024-12-31",
        initial_capital=1_000_000_000,
    )

    if result.success:
        logger.info("Backtest submitted: %s", result.value)
    else:
        logger.error("Backtest failed: %s", result.error)


if __name__ == "__main__":
    asyncio.run(main())
