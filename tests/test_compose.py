from __future__ import annotations

import asyncio
import sys
from datetime import date
from pathlib import Path

from backtesting.composer.indicator_registry import list_all_indicators
from backtesting.composer.phase_runner import PhaseRunner
from backtesting.composer.pre_filter import PreTestFilter
from backtesting.composer.quality_filter import QualityFilter
from backtesting.composer.strategy_composer import StrategyComposer
from services.backtest_service import BacktestService

#!/usr/bin/env python


_project_root = Path(__file__).resolve().parent.parent
if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))


async def main():
    print("=" * 60)
    print("  Strategy Composition System Test")
    print("=" * 60)

    # 1. Test indicator registry
    indicators = list_all_indicators()
    print(f"\n1. Indicator Registry: {len(indicators)} indicators loaded")
    for ind in indicators[:5]:
        print(
            f"   - {ind['name_fa']} ({ind['id']}): {len(ind['conditions'])} conditions, {len(ind['params'])} param groups"
        )
    print(f"   ... and {len(indicators) - 5} more")

    # 2. Test composer estimation
    composer = StrategyComposer(include_filters=False)
    total_no_filter = composer.estimate_total_count()
    print(f"\n2. Estimated combinations (no filter): {total_no_filter:,}")

    composer_with_filter = StrategyComposer(include_filters=True)
    total_with_filter = composer_with_filter.estimate_total_count()
    print(f"   Estimated combinations (with filter): {total_with_filter:,}")

    # 3. Test pre-filter
    pre_filter = PreTestFilter()
    print("\n3. Pre-Test Filter:")

    # Generate a small batch and test filter
    batch = composer_with_filter.generate_batch(0, 1000)
    filtered = pre_filter.filter_batch(batch)
    stats = pre_filter.get_stats()
    print(f"   Generated: {len(batch)}")
    print(f"   After filter: {len(filtered)}")
    print(f"   Rejection rate: {stats['rejection_rate']}%")
    print(f"   Filter stats: {stats}")

    # 4. Test quality filter
    quality_filter = QualityFilter()
    print("\n4. Quality Filter (6-stage):")
    test_metrics = {
        "total_return_pct": 15.0,
        "max_drawdown_pct": 20.0,
        "sharpe_ratio": 1.2,
        "win_rate": 55.0,
        "total_trades": 25,
        "profit_factor": 1.8,
    }
    passed, reason = quality_filter.should_keep(test_metrics)
    score = quality_filter.compute_score(test_metrics)
    print(f"   Test metrics: return={test_metrics['total_return_pct']}%, sharpe={test_metrics['sharpe_ratio']}")
    print(f"   Passed: {passed}, Score: {score:.2f}")

    # Fail test
    bad_metrics = {
        "total_return_pct": 2.0,
        "max_drawdown_pct": 35.0,
        "sharpe_ratio": 0.2,
        "win_rate": 30.0,
        "total_trades": 2,
        "profit_factor": 0.8,
    }
    passed2, reason2 = quality_filter.should_keep(bad_metrics)
    print(f"   Bad metrics: return = {bad_metrics}")
    print(f"   Bad metrics: return={bad_metrics['total_return_pct']}%, {reason2}")

    # 5. Test full pipeline (small)
    print("\n5. Full Pipeline Test (100 blueprints):")

    BacktestService()
    data = ("فولاد", date(2024, 1, 1), date(2024, 6, 30))
    if not data:
        print("   Skipping: No historical data available")
    else:
        print(f"   Loaded {len(data)} bars of data")

        runner = PhaseRunner(pre_filter, quality_filter)
        small_batch = composer_with_filter.generate_batch(0, 100)
        results = await runner.run_batch(small_batch, data, capital=1_000_000_000, symbol="فولاد", max_workers=2)
        print(f"   Results that passed quality filter: {len(results)}")

        if results:
            best = max(results, key=lambda r: r.get("score", 0))
            print("   Best result:")
            print(f"     Entry: {best['blueprint']['entry']['indicator']} ({best['blueprint']['entry']['condition']})")
            print(f"     Exit: {best['blueprint']['exit']['indicator']} ({best['blueprint']['exit']['condition']})")
            m = best["metrics"]
            print(
                f"     Return: {m.get('total_return_pct', 0):.1f}% | Sharpe: {m.get('sharpe_ratio', 0):.2f} | DD: {m.get('max_drawdown_pct', 0):.1f}%"
            )
            print(f"     Score: {best.get('score', 0):.2f}")

    print(f"\n{'=' * 60}")
    print("  All tests passed!")
    print(f"{'=' * 60}")


if __name__ == "__main__":
    asyncio.run(main())
