#!/usr/bin/env python
"""Run all backtests on a single symbol and generate comprehensive report."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import asyncio
import json
import time
from datetime import date

import core.database as _db


async def run_all():
    await _db.init_database()

    async with _db.async_session_factory() as session:
        from sqlalchemy import text

        result = await session.execute(text("""
            SELECT symbol, COUNT(*) as cnt
            FROM brsapi_historical_daily
            WHERE symbol IS NOT NULL AND symbol != ''
              AND price_close IS NOT NULL AND price_close > 0
            GROUP BY symbol
            HAVING COUNT(*) > 50
            ORDER BY cnt DESC
            LIMIT 1
        """))
        row = result.fetchone()
        if not row:
            print("ERROR: No symbols with enough data found.")
            return

        symbol = row[0]
        bar_count = row[1]
        print(f"Using symbol: {symbol} ({bar_count} bars)")

    from services.backtest_service import BacktestService

    svc = BacktestService()
    strategies = svc.list_strategies()

    # Filter out strategies that can't run on single symbol or are too slow
    excluded = {
        "equal_weight", "max_sharpe", "minimum_variance", "risk_parity", "tactical_allocation",
        "ml_signal",       # needs trained model
        "squeeze_momentum",  # O(n²), impractical for large datasets
    }
    single_symbol_strategies = [s for s in strategies if s.get("name") not in excluded]

    start = date(2024, 1, 1)
    end = date(2025, 6, 30)
    capital = 1_000_000_000

    print(f"Running {len(single_symbol_strategies)} strategies on {symbol}...")
    print(f"Period: {start} to {end} | Capital: {capital:,.0f} Rials")
    print("=" * 80)

    results = []
    for s in single_symbol_strategies:
        name = s.get("name", "?")
        print(f"  {name:<25}", end="", flush=True)
        t0 = time.time()
        try:
            r = await svc.run_backtest(
                name=f"{name}-{symbol}",
                symbols=[symbol],
                strategy_type=name,
                start_date=start,
                end_date=end,
                capital=capital,
                sizing_method="percent",
                sizing_value=90.0,  # use 90% of capital per trade
            )
            elapsed = time.time() - t0
            if r.success:
                resp = r.value
                run_id = resp.id
                full = await svc.get_result(run_id)
                metrics = full.value.get("metrics", {}) if (full.success and full.value) else {}
                ret = metrics.get("total_return_pct", 0)
                sharpe = metrics.get("sharpe_ratio", 0)
                max_dd = metrics.get("max_drawdown_pct", 0)
                win_rate = metrics.get("win_rate", 0)
                total_trades = int(metrics.get("total_trades", 0))
                profit_factor = metrics.get("profit_factor", 0)
                print(f"OK  {elapsed:5.1f}s  Return: {ret:>8.2f}%  Sharpe: {sharpe:>6.2f}  Trades: {total_trades}")
                results.append({
                    "strategy": name,
                    "return_pct": ret,
                    "sharpe": sharpe,
                    "max_drawdown": max_dd,
                    "win_rate": win_rate,
                    "total_trades": total_trades,
                    "profit_factor": profit_factor,
                    "elapsed_sec": round(elapsed, 1),
                })
            else:
                err = str(r.error) if r.error else "unknown"
                print(f"FAIL {elapsed:5.1f}s  {err[:50]}")
                results.append({"strategy": name, "error": err, "elapsed_sec": round(elapsed, 1)})
        except Exception as e:
            elapsed = time.time() - t0
            print(f"ERR  {elapsed:5.1f}s  {e}")
            results.append({"strategy": name, "error": str(e), "elapsed_sec": round(elapsed, 1)})

    # Sort by return (errors at bottom)
    results.sort(key=lambda x: x.get("return_pct", -9999), reverse=True)

    print()
    print("=" * 80)
    print(f"  COMPREHENSIVE BACKTEST REPORT: {symbol}")
    print(f"  Period: {start} to {end}")
    print(f"  Initial Capital: {capital:,.0f} Rials")
    print("=" * 80)
    header = f"{'Strategy':<25} {'Return%':>10} {'Sharpe':>8} {'MaxDD%':>8} {'WinRate':>8} {'Trades':>8} {'Time':>6}"
    print(header)
    print("-" * 80)
    for r in results:
        if "error" in r:
            print(f"{r['strategy']:<25} ERROR: {r['error'][:50]}")
        else:
            print(
                f"{r['strategy']:<25} "
                f"{r['return_pct']:>10.2f} "
                f"{r['sharpe']:>8.2f} "
                f"{r['max_drawdown']:>8.2f} "
                f"{r['win_rate']:>8.1f} "
                f"{r['total_trades']:>8} "
                f"{r['elapsed_sec']:>5.0f}s"
            )

    successful = [r for r in results if "error" not in r]
    if successful:
        top = successful[0]
        print()
        print(f"BEST: {top['strategy']}")
        print(f"  Return: {top['return_pct']:.2f}% | Sharpe: {top['sharpe']:.2f} | MaxDD: {top['max_drawdown']:.2f}% | WinRate: {top['win_rate']:.1f}% | Trades: {top['total_trades']}")

    report_path = f"backtest_report_{symbol}.json"
    with open(report_path, "w", encoding="utf-8") as f:
        json.dump({"symbol": symbol, "period": f"{start} to {end}", "results": results}, f, ensure_ascii=False, indent=2)
    print(f"\nReport saved to {report_path}")


if __name__ == "__main__":
    asyncio.run(run_all())
