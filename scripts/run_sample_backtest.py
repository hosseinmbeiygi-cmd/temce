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
from datetime import date

from core.logging import get_logger
from services.backtest_service import BacktestService

logger = get_logger(__name__)


async def main() -> None:
    service = BacktestService()

    # Test 1: Basic backtest with position sizing
    result = await service.run_backtest(
        name="Test SMA with Position Sizing",
        symbols=["فولاد"],
        strategy_type="moving_average_cross",
        strategy_params={"fast_period": 5, "slow_period": 20},
        start_date=date(2024, 1, 1),
        end_date=date(2024, 12, 31),
        capital=1_000_000_000,
        sizing_method="percent",
        sizing_value=10.0,  # 10% of capital per trade
    )

    if result.success:
        run_id = result.value.id
        print(f"Backtest submitted: id={run_id}")

        # Get full result
        full = await service.get_result(run_id)
        if full.success and full.value:
            r = full.value
            print("=== RESULTS ===")
            print(f"Total Return: {r.get('total_return_pct', 0):.2f}%")
            print(f"Sharpe Ratio: {r.get('sharpe_ratio', 0):.2f}")
            print(f"Max Drawdown: {r.get('max_drawdown_pct', 0):.2f}%")
            print(f"Win Rate: {r.get('win_rate', 0):.2f}%")
            print(f"Total Trades: {r.get('total_trades', 0)}")

            metrics = r.get("metrics", {})
            print(f"Sortino: {metrics.get('sortino_ratio', 0):.2f}")
            print(f"Calmar: {metrics.get('calmar_ratio', 0):.2f}")
            print(f"Omega: {metrics.get('omega_ratio', 0):.2f}")
            print(f"Tail Ratio: {metrics.get('tail_ratio', 0):.2f}")
            print(f"Pain Index: {metrics.get('pain_index', 0):.4f}")

            dq = r.get("data_quality")
            if dq:
                print(f"Data Quality Score: {dq.get('quality_score', 0):.3f}")
                print(f"Bad Ticks: {dq.get('n_bad_ticks', 0)}")
    else:
        print(f"Backtest failed: {result.error}")


if __name__ == "__main__":
    asyncio.run(main())
