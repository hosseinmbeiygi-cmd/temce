#!/usr/bin/env python
"""Single-symbol diagnostic test for the backtest pipeline."""

from __future__ import annotations

import asyncio
import sys
import traceback
from datetime import date
from pathlib import Path

_project_root = Path(__file__).resolve().parent.parent
if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))

import core.database as _db
from services.backtest_service import BacktestService

CAPITAL = 1_000_000_000


async def pick_symbol() -> str:
    from sqlalchemy import text
    async with _db.async_session_factory() as session:
        result = await session.execute(text("""
            SELECT symbol, COUNT(*) as cnt
            FROM brsapi_historical_daily
            WHERE price_close IS NOT NULL AND price_close > 0
            GROUP BY symbol HAVING COUNT(*) >= 200
            ORDER BY cnt DESC LIMIT 5
        """))
        rows = result.fetchall()
        if not rows:
            raise RuntimeError("No symbols with >=200 bars found")
        print(f"Candidate symbols: {[r[0] for r in rows]}")
        return rows[0][0]


async def test_single_strategy(symbol: str):
    print(f"\n{'='*70}")
    print(f"  TEST 1: Single Strategy Run — {symbol}")
    print(f"{'='*70}")

    from backtesting.engine.simulator import BacktestSimulator
    from backtesting.strategies.registry import get_strategy_registry, register_all_strategies

    register_all_strategies()
    registry = get_strategy_registry()

    svc = BacktestService()
    today = date.today()
    start = date(today.year - 2, 1, 1)
    end = today

    data = await svc._load_historical_data(symbol, start, end, source="historical")
    if not data:
        print("  SKIP: No data")
        return
    print(f"  Data: {len(data)} bars")

    simulator = BacktestSimulator()
    cls = registry.get("moving_average_cross")
    strategy = cls(fast_period=5, slow_period=20, instrument_id=symbol)
    result = simulator.run(strategy, initial_capital=CAPITAL, data=data)
    if result.success:
        bt = result.value
        print(f"  PASS: {len(bt.equity_curve)} bars, {len(bt.trades)} trades, return={bt.total_return_pct:.2f}%")
    else:
        print(f"  FAIL: {result.error}")


async def test_signal_strategy(symbol: str):
    print(f"\n{'='*70}")
    print(f"  TEST 2: SignalStrategy + RSI — {symbol}")
    print(f"{'='*70}")

    from backtesting.composer.indicator_registry import get_indicator
    from backtesting.engine.simulator import BacktestSimulator
    from backtesting.strategies.signal_strategy import SignalStrategy

    svc = BacktestService()
    today = date.today()
    start = date(today.year - 2, 1, 1)
    end = today

    data = await svc._load_historical_data(symbol, start, end, source="historical")
    if not data:
        print("  SKIP: No data")
        return

    close = [b["close"] for b in data]
    spec = get_indicator("rsi")
    if spec is None:
        print("  FAIL: RSI not found")
        return

    try:
        result = spec.compute_fn(close=close, period=14)
        if not result:
            print("  FAIL: RSI returned None")
            return

        entry_sig = [bool(v) for v in result.get("oversold", [False] * len(close))]
        exit_sig = [bool(v) for v in result.get("overbought", [False] * len(close))]
        print(f"  RSI signals: {sum(entry_sig)} entries, {sum(exit_sig)} exits")

        if sum(entry_sig) == 0 or sum(exit_sig) == 0:
            print("  SKIP: No signals")
            return

        strategy = SignalStrategy(
            entry_signal=entry_sig, exit_signal=exit_sig, name="RSI_14",
            instrument_id=symbol, sizing_method="fixed", sizing_value=CAPITAL * 0.1,
        )
        simulator = BacktestSimulator()
        result = simulator.run(strategy, initial_capital=CAPITAL, data=data)
        if result.success:
            bt = result.value
            print(f"  PASS: {len(bt.trades)} trades, return={bt.total_return_pct:.2f}%")
        else:
            print(f"  FAIL: {result.error}")
    except Exception as e:
        print(f"  ERROR: {e}")
        traceback.print_exc()


async def test_all_strategies(symbol: str):
    print(f"\n{'='*70}")
    print(f"  TEST 3: All Strategy Types — {symbol}")
    print(f"{'='*70}")

    from backtesting.engine.simulator import BacktestSimulator
    from backtesting.strategies.registry import get_strategy_registry, register_all_strategies

    register_all_strategies()
    registry = get_strategy_registry()

    svc = BacktestService()
    today = date.today()
    start = date(today.year - 2, 1, 1)
    end = today

    data = await svc._load_historical_data(symbol, start, end, source="historical")
    if not data:
        print("  SKIP: No data")
        return
    print(f"  Data: {len(data)} bars\n")

    import inspect
    test_configs = {
        "moving_average_cross": {"fast_period": 5, "slow_period": 20, "instrument_id": symbol},
        "momentum": {"lookback": 10, "threshold_pct": 2.0, "instrument_id": symbol},
        "mean_reversion": {"lookback": 20, "entry_z": 2.0, "exit_z": 0.5, "instrument_id": symbol},
        "breakout": {"lookback": 20, "breakout_pct": 1.0, "instrument_id": symbol},
        "rsi_reversion": {"period": 14, "oversold": 30, "overbought": 70, "instrument_id": symbol},
        "volatility_breakout": {"lookback": 20, "multiplier": 2.0, "instrument_id": symbol},
        "half_trend": {"amplitude": 2, "channel_deviation": 2.0, "instrument_id": symbol},
        "support_resistance": {"lookback": 20, "vol_threshold": 1.5, "instrument_id": symbol},
    }

    simulator = BacktestSimulator()
    ok_count = 0
    for name, params in test_configs.items():
        cls = registry.get(name)
        if cls is None:
            print(f"  {name:<25} NOT REGISTERED")
            continue
        sig = inspect.signature(cls.__init__)
        accepted = set(sig.parameters.keys()) - {"self"}
        filtered = {k: v for k, v in params.items() if k in accepted}
        try:
            strategy = cls(**filtered)
            result = simulator.run(strategy, initial_capital=CAPITAL, data=data)
            if result.success:
                bt = result.value
                ok_count += 1
                print(f"  {name:<25} OK  trades={len(bt.trades):>4}  return={bt.total_return_pct:>8.2f}%")
            else:
                print(f"  {name:<25} FAIL: {result.error}")
        except Exception as e:
            print(f"  {name:<25} ERROR: {e}")
    print(f"\n  {ok_count}/{len(test_configs)} strategies OK")


async def test_all_indicators(symbol: str):
    print(f"\n{'='*70}")
    print(f"  TEST 4: All Indicators — {symbol}")
    print(f"{'='*70}")

    from backtesting.composer.indicator_registry import INDICATOR_REGISTRY

    svc = BacktestService()
    today = date.today()
    start = date(today.year - 2, 1, 1)
    end = today

    data = await svc._load_historical_data(symbol, start, end, source="historical")
    if not data:
        print("  SKIP: No data")
        return
    print(f"  Data: {len(data)} bars\n")

    close = [b["close"] for b in data]
    high = [b.get("high", b["close"]) for b in data]
    low = [b.get("low", b["close"]) for b in data]
    volume = [b.get("volume", 0) for b in data]

    import inspect
    extra = {"buy_val", "buy_cnt", "sell_val", "sell_cnt", "net_flow", "free_float",
             "sell_pressure", "ret", "asset_price", "benchmark_price"}

    ok_count = 0
    for spec in INDICATOR_REGISTRY:
        sig = inspect.signature(spec.compute_fn)
        param_names = set(sig.parameters.keys())
        missing = [a for a in extra if a in param_names]
        if missing:
            print(f"  {spec.id:<30} SKIP (needs: {missing})")
            continue

        fn = spec.compute_fn
        arg_names = fn.__code__.co_varnames[:fn.__code__.co_argcount]
        kwargs = {}
        if "close" in arg_names:
            kwargs["close"] = close
        if "high" in arg_names:
            kwargs["high"] = high
        if "low" in arg_names:
            kwargs["low"] = low
        if "volume" in arg_names:
            kwargs["volume"] = volume
        if "prices" in arg_names:
            kwargs["prices"] = close

        for pk, pv in spec.params.items():
            if pk not in kwargs:
                kwargs[pk] = pv[0] if isinstance(pv, list) and pv else pv if not isinstance(pv, list) else 14

        try:
            result = fn(**kwargs)
            if result is None:
                print(f"  {spec.id:<30} NULL")
                continue
            keys = list(result.keys()) if isinstance(result, dict) else []
            ok_count += 1
            print(f"  {spec.id:<30} OK  keys={keys}")
        except Exception as e:
            print(f"  {spec.id:<30} ERROR: {e}")

    print(f"\n  {ok_count}/{len(INDICATOR_REGISTRY)} indicators OK")


async def test_strategy_generator(symbol: str):
    print(f"\n{'='*70}")
    print(f"  TEST 5: StrategyGenerator — {symbol}")
    print(f"{'='*70}")

    from services.strategy_generator import get_strategy_generator

    gen = get_strategy_generator()
    gen._running = False
    gen._phase = "idle"

    today = date.today()
    start = date(today.year - 2, 1, 1)
    end = today

    try:
        result = await gen.generate(
            symbols=[symbol],
            start_date=start,
            end_date=end,
            capital=CAPITAL,
            max_combinations=20,
            use_genetic=False,
            filters={
                "stage1_min_return": 5.0, "stage2_max_drawdown": 25.0,
                "stage3_min_sharpe": 0.5, "stage4_min_win_rate": 40.0,
                "stage5_min_trades": 5, "stage6_min_profit_factor": 1.2,
            },
        )
        if result.success:
            data = result.value
            strategies = data.get("strategies", [])
            stats = data.get("stats", {})
            print(f"  PASS: {stats.get('total_combinations', 0)} combos → {len(strategies)} passed")
            if strategies:
                best = strategies[0]
                print(f"  Best: {best['strategy']} score={best['score']:.3f} return={best['metrics'].get('total_return_pct', 0):.1f}%")
        else:
            print(f"  FAIL: {result.error}")
    except Exception as e:
        print(f"  ERROR: {e}")
        traceback.print_exc()


async def main():
    await _db.init_database()
    if _db.async_session_factory is None:
        print("ERROR: Database not available")
        return

    symbol = await pick_symbol()
    print(f"\nTesting with symbol: {symbol}\n")

    await test_single_strategy(symbol)
    await test_signal_strategy(symbol)
    await test_all_strategies(symbol)
    await test_all_indicators(symbol)
    await test_strategy_generator(symbol)

    print(f"\n{'='*70}")
    print("  ALL TESTS COMPLETE")
    print(f"{'='*70}")


if __name__ == "__main__":
    asyncio.run(main())
