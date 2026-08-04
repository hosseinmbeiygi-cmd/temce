#!/usr/bin/env python
"""Quick check: what's in the metrics after a backtest."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import asyncio
from datetime import date

import core.database as _db


async def debug():
    await _db.init_database()

    from services.backtest_service import BacktestService
    svc = BacktestService()

    r = await svc.run_backtest(
        name="debug-winrate",
        symbols=["فولاد"],
        strategy_type="moving_average_cross",
        start_date=date(2024, 1, 1),
        end_date=date(2025, 6, 30),
        capital=1_000_000_000,
        sizing_method="percent",
        sizing_value=90.0,
    )
    if r.success:
        run_id = r.value.id
        full = await svc.get_result(run_id)
        if full.success and full.value:
            metrics = full.value.get("metrics", {})
            print(f"Metrics keys: {sorted(metrics.keys())}")
            print(f"win_rate: {metrics.get('win_rate', 'MISSING')}")
            print(f"total_trades: {metrics.get('total_trades', 'MISSING')}")
            print(f"total_return_pct: {metrics.get('total_return_pct', 'MISSING')}")
            print(f"profit_factor: {metrics.get('profit_factor', 'MISSING')}")
            print(f"total_pnl: {metrics.get('total_pnl', 'MISSING')}")
        else:
            print(f"get_result failed: {full}")

        # Also check _runs
        if run_id in svc._runs:
            runs_entry = svc._runs[run_id]
            print(f"\n_runs keys: {sorted(runs_entry.keys())}")
            print(f"_runs has metrics: {'metrics' in runs_entry}")
        else:
            print(f"\nrun_id {run_id} NOT in _runs")

        # Check repo directly
        repo_result = await svc._repo.get(run_id)
        if repo_result.success and repo_result.value:
            ent = repo_result.value
            print(f"\nRepo entity extra keys: {sorted(ent.extra.keys()) if ent.extra else 'EMPTY'}")
            print(f"Repo entity extra has win_rate: {'win_rate' in (ent.extra or {})}")


if __name__ == "__main__":
    asyncio.run(debug())
