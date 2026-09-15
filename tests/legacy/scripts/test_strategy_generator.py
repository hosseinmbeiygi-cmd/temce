#!/usr/bin/env python
from __future__ import annotations

import sys
from pathlib import Path

_project_root = Path(__file__).resolve().parents[3]
if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))

import asyncio
from datetime import date

from services.strategy_generator import get_strategy_generator


async def main() -> None:
    gen = get_strategy_generator()

    print("=== Strategy Generator Test ===")
    print("Running on symbol: فولاد")
    print("Max combinations: 500")
    print("Genetic: ON (8 generations)")
    print()

    result = await gen.generate(
        symbols=["فولاد"],
        start_date=date(2023, 1, 1),
        end_date=date(2024, 12, 31),
        capital=1_000_000_000,
        max_combinations=500,
        use_genetic=True,
        genetic_generations=8,
    )

    if result.success:
        data = result.value
        print("\n=== RESULTS ===")
        print(f"Total strategies tested: {data.get('total_tested', 0)}")
        print(f"Passed filters: {data.get('passed', 0)}")
        print(f"Unique strategies: {data.get('unique', 0)}")

        top = data.get("top_results", [])
        if top:
            print("\n=== TOP 5 STRATEGIES ===")
            for i, r in enumerate(top[:5], 1):
                m = r.get("metrics", {})
                print(f"\n#{i} | {r.get('strategy', '?')} | Score: {r.get('score', 0):.2f}")
                print(f"   Params: {r.get('params', {})}")
                print(
                    f"   Return: {m.get('total_return_pct', 0):.1f}% | Sharpe: {m.get('sharpe_ratio', 0):.2f} | DD: {m.get('max_drawdown_pct', 0):.1f}%"
                )
                print(
                    f"   Win Rate: {m.get('win_rate', 0):.0f}% | Trades: {m.get('total_trades', 0)} | PF: {m.get('profit_factor', 0):.2f}"
                )
        else:
            print("No strategies passed the 6-stage filter.")
    else:
        print(f"Failed: {result.error}")


if __name__ == "__main__":
    asyncio.run(main())

