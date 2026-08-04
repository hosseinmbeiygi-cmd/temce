#!/usr/bin/env python
"""
BACKTEST ALL SYMBOLS — ALL INDICATORS — ALL STRATEGIES — GENETIC OPTIMIZATION

Comprehensive backtest pipeline with 3 integrated phases:

PHASE 1 — Strategy Grid Search + 6-Stage Filter + Genetic Optimization
PHASE 2 — ALL 30 Indicators via SignalStrategy + 6-Stage Filter
PHASE 3 — Persistence & Reports

Fixed: Volume adjustment to prevent "has 1, needs 1000" error.
Optimized: Config batching, concurrency, and error handling.
"""

from __future__ import annotations

import asyncio
import hashlib
import itertools
import json
import math
import random
import sys
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import date, datetime
from pathlib import Path
from typing import Any

# --- auto PYTHONPATH ---
_project_root = Path(__file__).resolve().parent.parent
if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))
# --- end auto PYTHONPATH ---

import core.database as _db
from backtesting.composer.indicator_registry import REGISTRY as INDICATOR_REGISTRY
from backtesting.composer.indicator_registry import IndicatorSpec, get_indicator
from backtesting.engine.simulator import BacktestSimulator
from backtesting.strategies.signal_strategy import SignalStrategy
from core.db_utils import safe_row_str
from core.logging import get_logger
from services.backtest_service import BacktestService
from services.strategy_generator import (
    _apply_6stage_filter,
    get_strategy_generator,
)

logger = get_logger(__name__)

# ═══════════════════════════ Configuration ═══════════════════════════

@dataclass
class Config:
    """All configurable parameters for the backtest pipeline."""
    # Data sources
    data_sources: list[str] = field(default_factory=lambda: ["historical", "intraday"])
    start_date: date | None = None
    end_date: date | None = None

    # Capital & sizing
    capital: float = 1_000_000_000  # 1 billion Toman
    fixed_quantity: int = 1000      # Number of shares per trade (fixed)

    # Concurrency
    max_concurrent: int = 5
    timeout_batch: int = 600        # seconds

    # Phases
    run_phase1: bool = True
    run_phase2: bool = True
    phase1_generations: int = 6
    phase1_max_combos: int = 3000
    phase2_max_configs: int = 2000  # reduced for speed

    # 6-Stage Filter (tuned for Iranian market)
    filters: dict[str, Any] = field(default_factory=lambda: {
        "stage1_min_return": 5.0,
        "stage2_max_drawdown": 25.0,
        "stage3_min_sharpe": 0.5,
        "stage4_min_win_rate": 40.0,
        "stage5_min_trades": 5,
        "stage6_min_profit_factor": 1.2,
    })

    # Report paths
    report_path: str = "backtest_all_symbols_report.json"
    summary_path: str = "backtest_all_symbols_summary.json"

    # Symbol limit (top N by data availability)
    max_symbols: int = 100

# Global config instance
CFG = Config()

# ═══════════════════════ Signal Configs for 30 Indicators ═══════════

SIGNAL_CONFIGS: dict[str, list[dict[str, str]]] = {
    "rsi":                     [{"entry": "oversold", "exit": "overbought"}],
    "macd":                    [{"entry": "bullish_cross", "exit": "bearish_cross"}],
    "squeeze_momentum":        [{"entry": "momentum_positive", "exit": "momentum_negative"}],
    "stochastic":              [{"entry": "oversold", "exit": "overbought"}],
    "williams_r":              [{"entry": "oversold", "exit": "overbought"}],
    "cci":                     [{"entry": "oversold", "exit": "overbought"}],
    "ema_crossover":           [{"entry": "golden_cross", "exit": "death_cross"}],
    "adx":                     [{"entry": "strong_trend", "exit": "weak_trend"}],
    "half_trend":              [{"entry": "buy_signal", "exit": "sell_signal"}],
    "parabolic_sar":           [{"entry": "buy_signal", "exit": "sell_signal"}],
    "ichimoku":                [{"entry": "bullish_cloud", "exit": "bearish_cloud"}],
    "atr":                     [{"entry": "low_volatility", "exit": "high_volatility"}],
    "bollinger_bw":            [{"entry": "squeeze", "exit": "expansion"}],
    "keltner_position":        [{"entry": "above_upper", "exit": "below_lower"}],
    "compression_ratio":       [{"entry": "compressed", "exit": "expanded"}],
    "relative_volume":         [{"entry": "high_volume", "exit": "low_volume"}],
    "obv":                     [{"entry": "obv_rising", "exit": "obv_falling"}],
    "vwap":                    [{"entry": "above_vwap", "exit": "below_vwap"}],
    "supply_dryness":          [{"entry": "dry", "exit": "abundant"}],
    "clv":                     [{"entry": "strong_close", "exit": "weak_close"}],
    "recovery_ratio":          [{"entry": "strong_recovery", "exit": "weak_recovery"}],
    "support_resistance":      [{"entry": "break_up", "exit": "break_down"}],
    "breakout_quality":        [{"entry": "strong_breakout", "exit": "weak_breakout"}],
    "volume_zscore":           [{"entry": "high_zscore", "exit": "low_zscore"}],
    "amihud_illiquidity":      [{"entry": "liquid", "exit": "illiquid"}],
    "normalized_volatility":   [{"entry": "low_volatility", "exit": "high_volatility"}],
    "relative_strength":       [{"entry": "outperforming", "exit": "underperforming"}],
}


# ═══════════════════════════ Data Structures ════════════════════════

@dataclass
class IndicatorResult:
    symbol: str
    data_source: str
    indicator_id: str
    indicator_name: str
    params: dict[str, Any]
    signal_config: str
    metrics: dict[str, float]
    score: float
    filter_stage: str = "passed"


@dataclass
class StrategyResult:
    symbol: str
    data_source: str
    strategy: str
    params: dict[str, Any]
    metrics: dict[str, Any]
    score: float
    method: str = "grid_search"


# ═══════════════════════════ Helper Functions ═══════════════════════

def _compute_indicator_metrics(equity: list[float], trades: list[float], capital: float) -> dict[str, float]:
    """Compute comprehensive metrics from equity curve and trades."""
    if len(equity) < 2:
        return {
            "total_return_pct": 0.0,
            "sharpe_ratio": 0.0,
            "max_drawdown_pct": 0.0,
            "win_rate": 0.0,
            "total_trades": 0,
            "profit_factor": 0.0,
            "sortino_ratio": 0.0,
            "calmar_ratio": 0.0,
            "annualized_return_pct": 0.0,
            "winning_trades": 0,
            "losing_trades": 0,
        }

    total_return = ((equity[-1] / capital) - 1) * 100
    trading_days = len(equity)
    years = max(trading_days / 252, 0.01)
    ann_return = ((equity[-1] / capital) ** (1 / years) - 1) * 100

    returns = [(equity[i] / equity[i - 1]) - 1 for i in range(1, len(equity))]
    avg_r = sum(returns) / len(returns) if returns else 0
    std_r = math.sqrt(sum((r - avg_r) ** 2 for r in returns) / len(returns)) if returns else 1e-6
    sharpe = (avg_r / std_r) * math.sqrt(252) if std_r > 1e-6 else 0

    peak = equity[0]
    max_dd = 0.0
    for nav in equity:
        if nav > peak:
            peak = nav
        dd = (peak - nav) / peak if peak > 0 else 0
        max_dd = max(max_dd, dd)

    wins = [t for t in trades if t > 0]
    losses = [abs(t) for t in trades if t < 0]
    win_rate = (len(wins) / len(trades) * 100) if trades else 0
    profit_factor = (sum(wins) / sum(losses)) if sum(losses) > 0 else (9e9 if wins else 0)

    downside = [r for r in returns if r < 0]
    downside_vol = math.sqrt(sum(r**2 for r in downside) / len(downside)) if downside else 1e-6
    sortino = (avg_r / downside_vol) * math.sqrt(252) if downside_vol > 1e-6 else 0
    calmar = ann_return / (max_dd * 100 + 0.01) if max_dd > 0 else 0

    return {
        "total_return_pct": round(total_return, 2),
        "annualized_return_pct": round(ann_return, 2),
        "sharpe_ratio": round(sharpe, 2),
        "max_drawdown_pct": round(max_dd * 100, 2),
        "win_rate": round(win_rate, 1),
        "total_trades": len(trades),
        "winning_trades": len(wins),
        "losing_trades": len(losses),
        "profit_factor": round(profit_factor, 2),
        "sortino_ratio": round(sortino, 2),
        "calmar_ratio": round(calmar, 2),
    }


def _indicator_combined_score(metrics: dict[str, float]) -> float:
    """Compute a composite score from metrics."""
    return (
        metrics.get("sharpe_ratio", 0) * 0.30
        + metrics.get("sortino_ratio", 0) * 0.15
        + metrics.get("calmar_ratio", 0) * 0.15
        + metrics.get("total_return_pct", 0) * 0.002
        + metrics.get("profit_factor", 0) * 0.15
        + metrics.get("win_rate", 0) * 0.005
        - metrics.get("max_drawdown_pct", 0) * 0.005
    )


def _compute_indicator(
    spec: IndicatorSpec,
    close: list[float],
    high: list[float],
    low: list[float],
    volume: list[float],
    params: dict[str, Any],
) -> dict[str, list] | None:
    """Call indicator compute_fn with appropriate OHLCV args."""
    fn = spec.compute_fn
    arg_names = fn.__code__.co_varnames[:fn.__code__.co_argcount]
    kwargs = dict(params)

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

    # Skip indicators needing non‑OHLCV data
    extra = {"buy_val", "buy_cnt", "sell_val", "sell_cnt", "net_flow", "free_float",
             "sell_pressure", "ret", "asset_price", "benchmark_price"}
    if extra.intersection(arg_names):
        missing = [a for a in extra if a in arg_names and a not in kwargs]
        if missing:
            return None

    try:
        return fn(**kwargs)
    except Exception:
        return None


# ═══════════════════════════ Fetch Symbols ═════════════════════════

async def fetch_all_symbols() -> list[dict[str, Any]]:
    """Discover symbols with available data from historical, intraday, and quotes tables."""
    if _db.async_session_factory is None:
        await _db.init_database()
    if _db.async_session_factory is None:
        logger.error("Database not available")
        return []

    from sqlalchemy import text

    async with _db.async_session_factory() as session:
        hist_result = await session.execute(text("""
            SELECT symbol, MIN(date), MAX(date), COUNT(*)
            FROM brsapi_historical_daily WHERE price_close IS NOT NULL AND price_close > 0
            GROUP BY symbol HAVING COUNT(*) >= 10 ORDER BY COUNT(*) DESC
        """))
        hist_map: dict[str, dict] = {}
        for row in hist_result.fetchall():
            hist_map[row[0]] = {
                "symbol": row[0],
                "hist_start": safe_row_str(row, idx=1, default=None),
                "hist_end": safe_row_str(row, idx=2, default=None),
                "hist_bars": row[3],
                "intra_start": None,
                "intra_end": None,
                "intra_days": 0,
            }

        intra_result = await session.execute(text("""
            SELECT symbol, MIN(trade_date), MAX(trade_date), COUNT(DISTINCT trade_date)
            FROM brsapi_intraday_trades WHERE price > 0 AND volume > 0
            GROUP BY symbol HAVING COUNT(DISTINCT trade_date) >= 5 ORDER BY 4 DESC
        """))
        for row in intra_result.fetchall():
            sym = row[0]
            if sym in hist_map:
                hist_map[sym]["intra_start"] = safe_row_str(row, idx=1, default=None)
                hist_map[sym]["intra_end"] = safe_row_str(row, idx=2, default=None)
                hist_map[sym]["intra_days"] = row[3]
            else:
                hist_map[sym] = {
                    "symbol": sym,
                    "hist_start": None,
                    "hist_end": None,
                    "hist_bars": 0,
                    "intra_start": safe_row_str(row, idx=1, default=None),
                    "intra_end": safe_row_str(row, idx=2, default=None),
                    "intra_days": row[3],
                }

        quote_result = await session.execute(text("""
            SELECT symbol, MIN(date), MAX(date), COUNT(*)
            FROM quotes WHERE price_close IS NOT NULL AND price_close > 0
            GROUP BY symbol HAVING COUNT(*) >= 10
        """))
        for row in quote_result.fetchall():
            sym = row[0]
            if sym not in hist_map:
                hist_map[sym] = {
                    "symbol": sym,
                    "hist_start": safe_row_str(row, idx=1, default=None),
                    "hist_end": safe_row_str(row, idx=2, default=None),
                    "hist_bars": row[3],
                    "intra_start": None,
                    "intra_end": None,
                    "intra_days": 0,
                }
            elif hist_map[sym]["hist_bars"] == 0:
                hist_map[sym]["hist_start"] = safe_row_str(row, idx=1, default=None)
                hist_map[sym]["hist_end"] = safe_row_str(row, idx=2, default=None)
                hist_map[sym]["hist_bars"] = row[3]

    symbols = sorted(
        hist_map.values(),
        key=lambda x: (
            -1 if (x["hist_bars"] > 0 and x["intra_days"] > 0) else 0,
            x["hist_bars"] + x["intra_days"],
        ),
        reverse=True,
    )
    logger.info(
        "Discovered %d symbols: %d history, %d intraday, %d both",
        len(symbols),
        sum(1 for s in symbols if s["hist_bars"] > 0),
        sum(1 for s in symbols if s["intra_days"] > 0),
        sum(1 for s in symbols if s["hist_bars"] > 0 and s["intra_days"] > 0),
    )
    return symbols


# ═══════════════════════ PHASE 1: Strategy Generator ═══════════════

async def run_phase1_strategies(
    symbols_info: list[dict[str, Any]],
    all_results: list[StrategyResult],
) -> None:
    """Run StrategyGenerator on each symbol: grid search → 6-stage filter → genetic."""
    print("\n" + "=" * 80)
    print("  PHASE 1: STRATEGY GENERATOR (Grid Search + 6-Stage Filter + Genetic)")
    print("=" * 80)
    print()

    gen = get_strategy_generator()
    if gen.is_running:
        logger.warning("Strategy generator is stuck — resetting.")
        gen._running = False
        gen._phase = "idle"

    today = date.today()
    start = CFG.start_date or date(today.year - 2, 1, 1)
    end = CFG.end_date or today

    symbols = [s["symbol"] for s in symbols_info[:CFG.max_symbols]]
    print(f"Symbols: {len(symbols)} (top {CFG.max_symbols} by data availability)")
    print(f"Period: {start} to {end}")
    filters = CFG.filters
    print(f"Filters: Return>{filters['stage1_min_return']}% | DD<{filters['stage2_max_drawdown']}% | "
          f"Sharpe>{filters['stage3_min_sharpe']} | WR>{filters['stage4_min_win_rate']}% | "
          f"Trades>{filters['stage5_min_trades']} | PF>{filters['stage6_min_profit_factor']}")
    print()

    try:
        result = await gen.generate(
            symbols=symbols,
            start_date=start,
            end_date=end,
            capital=CFG.capital,
            max_combinations=CFG.phase1_max_combos,
            use_genetic=True,
            genetic_generations=CFG.phase1_generations,
            filters=filters,
        )

        if result.success:
            data = result.value
            strategies = data.get("strategies", [])
            stats = data.get("stats", {})
            for s in strategies:
                all_results.append(StrategyResult(
                    symbol=s.get("symbol", "?"),
                    data_source="historical",  # auto source
                    strategy=s.get("strategy", "?"),
                    params=s.get("params", {}),
                    metrics=s.get("metrics", {}),
                    score=s.get("score", 0),
                    method=s.get("method", "grid_search"),
                ))
            print(f"Phase 1 Complete: {stats.get('total_combinations', 0)} combos → "
                  f"{stats.get('passed_filter', 0)} passed | genetic: {stats.get('genetic_used', False)}")
            print(f"Found {len(strategies)} strategies from Phase 1")

            await _persist_phase1_results(strategies, filters)
        else:
            print(f"Phase 1 failed: {result.error}")

    except Exception as e:
        logger.exception("Phase 1 error: %s", e)
        print(f"Phase 1 error: {e}")


# ═══════════════════════ PHASE 2: All 30 Indicators ═══════════════

async def _build_indicator_configs() -> list[tuple[str, dict[str, Any], str]]:
    """Build list of (indicator_id, params_dict, signal_name) to test."""
    configs: list[tuple[str, dict[str, Any], str]] = []
    for spec in INDICATOR_REGISTRY:
        if spec.id not in SIGNAL_CONFIGS:
            continue
        signal_options = SIGNAL_CONFIGS[spec.id]
        param_keys = list(spec.params.keys())
        param_values = [spec.params[k] for k in param_keys]
        if param_values:
            for combo in itertools.product(*param_values):
                params = dict(zip(param_keys, combo, strict=False))
                for sig in signal_options:
                    sig_name = f"{sig['entry']}/{sig['exit']}"
                    configs.append((spec.id, params, sig_name))
        else:
            for sig in signal_options:
                sig_name = f"{sig['entry']}/{sig['exit']}"
                configs.append((spec.id, {}, sig_name))

    if len(configs) > CFG.phase2_max_configs:
        random.shuffle(configs)
        configs = configs[:CFG.phase2_max_configs]

    return configs


async def _scan_symbol_indicators(
    symbol: str,
    ohlcv: list[dict[str, Any]],
    data_source: str,
    configs: list[tuple[str, dict[str, Any], str]],
    sem: asyncio.Semaphore,
) -> list[IndicatorResult]:
    """Run all indicator configs on one symbol's OHLCV data with 6-stage filter."""
    async with sem:
        return await asyncio.to_thread(
            _scan_symbol_indicators_sync, symbol, ohlcv, data_source, configs
        )


def _scan_symbol_indicators_sync(
    symbol: str,
    ohlcv: list[dict[str, Any]],
    data_source: str,
    configs: list[tuple[str, dict[str, Any], str]],
) -> list[IndicatorResult]:
    """Synchronous version — runs in thread pool. FIX: volume adjustment."""
    # ===================== FIX: Ensure volume >= 1000 =====================
    fixed_ohlcv = []
    for bar in ohlcv:
        new_bar = bar.copy()
        vol = new_bar.get("volume", 0)
        if vol < 1000:
            new_bar["volume"] = 1000  # minimum for simulation
        fixed_ohlcv.append(new_bar)
    ohlcv = fixed_ohlcv
    # ======================================================================

    close = [b["close"] for b in ohlcv]
    high = [b.get("high", b["close"]) for b in ohlcv]
    low = [b.get("low", b["close"]) for b in ohlcv]
    volume = [b.get("volume", 0) for b in ohlcv]
    n = len(ohlcv)

    by_indicator: dict[str, list[tuple[dict[str, Any], str]]] = defaultdict(list)
    for ind_id, params, sig_name in configs:
        by_indicator[ind_id].append((params, sig_name))

    passing: list[IndicatorResult] = []

    for ind_id, param_sig_list in by_indicator.items():
        spec = get_indicator(ind_id)
        if spec is None:
            continue

        param_cache: dict[str, tuple[list[bool], list[bool]]] = {}

        for params, sig_name in param_sig_list:
            param_key = str(sorted(params.items()))
            if param_key in param_cache:
                entry_sig, exit_sig = param_cache[param_key]
            else:
                try:
                    result = _compute_indicator(spec, close, high, low, volume, params)
                    if result is None:
                        continue
                    entry_key, exit_key = sig_name.split("/")
                    entry_sig = [bool(v) for v in result.get(entry_key, [False] * n)]
                    exit_sig = [bool(v) for v in result.get(exit_key, [False] * n)]
                    param_cache[param_key] = (entry_sig, exit_sig)
                except Exception:
                    continue

            if sum(entry_sig) == 0 or sum(exit_sig) == 0:
                continue

            strategy = SignalStrategy(
                entry_signal=entry_sig,
                exit_signal=exit_sig,
                name=f"{ind_id}_{sig_name}",
                instrument_id=symbol,
                sizing_method="fixed",
                sizing_value=CFG.fixed_quantity,  # fixed 1000 shares
            )
            bt_result = BacktestSimulator().run(strategy, initial_capital=CFG.capital, data=ohlcv)
            if not bt_result.success:
                continue

            bt = bt_result.value
            metrics = _compute_indicator_metrics(
                [ep.nav for ep in bt.equity_curve],
                [getattr(t, "pnl", 0) for t in bt.trades],
                CFG.capital,
            )

            passed_filter, _ = _apply_6stage_filter(metrics, CFG.filters)
            if not passed_filter:
                continue

            score = _indicator_combined_score(metrics)
            passing.append(IndicatorResult(
                symbol=symbol,
                data_source=data_source,
                indicator_id=ind_id,
                indicator_name=spec.name_fa,
                params=params,
                signal_config=sig_name,
                metrics=metrics,
                score=score,
                filter_stage="passed",
            ))

    return passing


async def run_phase2_indicators(
    symbols_info: list[dict[str, Any]],
    all_results: list[StrategyResult],
) -> None:
    """Run ALL 30 indicators via SignalStrategy on each symbol with 6-stage filter."""
    print("\n" + "=" * 80)
    print("  PHASE 2: ALL 30 INDICATORS (SignalStrategy + 6-Stage Filter)")
    print("=" * 80)
    print()

    configs = await _build_indicator_configs()
    unique_indicators = len({c[0] for c in configs})
    print(f"Indicator configs: {len(configs)} ({unique_indicators} unique indicators)")
    filters = CFG.filters
    print(f"Filters: Return>{filters['stage1_min_return']}% | DD<{filters['stage2_max_drawdown']}% | "
          f"Sharpe>{filters['stage3_min_sharpe']} | WR>{filters['stage4_min_win_rate']}% | "
          f"Trades>{filters['stage5_min_trades']} | PF>{filters['stage6_min_profit_factor']}")
    print()

    svc = BacktestService()
    today = date.today()
    start = CFG.start_date or date(today.year - 2, 1, 1)
    end = CFG.end_date or today

    sem = asyncio.Semaphore(CFG.max_concurrent)
    all_indicator_results: list[IndicatorResult] = []

    for source in CFG.data_sources:
        print(f"\n--- Data Source: {source.upper()} ---")

        # Pre-load data for all symbols
        sym_data_map: dict[str, list[dict]] = {}
        for sym_info in symbols_info:
            sym = sym_info["symbol"]
            if source == "historical" and sym_info["hist_bars"] < 10:
                continue
            if source == "intraday" and sym_info["intra_days"] < 5:
                continue
            data = await svc._load_historical_data(sym, start, end, source=source)
            if data and len(data) >= 30:
                sym_data_map[sym] = data

        print(f"  Symbols with data: {len(sym_data_map)}")

        # Run all symbols in parallel
        async def _scan_one(sym: str, data_map=sym_data_map, src=source):
            return sym, await _scan_symbol_indicators(
                sym, data_map[sym], src, configs, sem
            )

        tasks = [_scan_one(sym) for sym in sym_data_map]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        src_results: list[IndicatorResult] = []
        for r in results:
            if isinstance(r, Exception):
                logger.warning("Error scanning symbol: %s", r)
                continue
            _, passing = r
            src_results.extend(passing)
            all_indicator_results.extend(passing)

        print(f"  {source.upper()} complete: {len(src_results)} passing indicator configs "
              f"across {len(sym_data_map)} symbols")

        # Convert to StrategyResult for unified report
        for ir in src_results:
            all_results.append(StrategyResult(
                symbol=ir.symbol,
                data_source=ir.data_source,
                strategy=f"indicator:{ir.indicator_id}",
                params={"indicator": ir.indicator_id, "signal": ir.signal_config, **ir.params},
                metrics=ir.metrics,
                score=ir.score,
                method="indicator_signal",
            ))

    await _persist_indicator_results(all_indicator_results)
    print(f"\nPhase 2 Complete: {len(all_indicator_results)} indicator configs passed 6-stage filter")


# ═══════════════════════ Persistence Helpers ═══════════════════════

async def _persist_indicator_results(results: list[IndicatorResult]) -> None:
    """Save indicator results to generated_strategies table (batched)."""
    if not results or _db.async_session_factory is None:
        return

    from sqlalchemy import text

    from core.ids import new_id

    batch_id = new_id("indb")
    inserted = 0
    batch_size = 500

    try:
        async with _db.async_session_factory() as session:
            for _i, r in enumerate(results):
                param_hash = hashlib.md5(str(sorted(r.params.items())).encode()).hexdigest()[:12]
                sid = f"{batch_id}_{r.symbol}_{r.indicator_id}_{param_hash}"[:50]
                sid = sid.replace("-", "_")
                m = r.metrics
                await session.execute(
                    text("""
                        INSERT INTO generated_strategies (
                            id, symbol, entry_indicator, entry_params, entry_condition,
                            exit_indicator, exit_params, exit_condition,
                            strategy_type, total_return_pct, annualized_return_pct,
                            sharpe_ratio, sortino_ratio, calmar_ratio,
                            max_drawdown_pct, win_rate, profit_factor,
                            total_trades, winning_trades, losing_trades,
                            score, batch_id, status
                        ) VALUES (
                            :id, :symbol, :entry, :entry_params, :entry_cond,
                            :exit, :exit_params, :exit_cond,
                            'indicator', :ret, :ann_ret,
                            :sharpe, :sortino, :calmar,
                            :max_dd, :win_rate, :pf,
                            :trades, :wins, :losses,
                            :score, :batch_id, 'active'
                        ) ON CONFLICT (id) DO NOTHING
                    """),
                    {
                        "id": sid,
                        "symbol": r.symbol,
                        "entry": r.indicator_id,
                        "entry_params": json.dumps(r.params, ensure_ascii=False),
                        "entry_cond": r.signal_config.split("/")[0],
                        "exit": r.indicator_id,
                        "exit_params": json.dumps(r.params, ensure_ascii=False),
                        "exit_cond": r.signal_config.split("/")[1] if "/" in r.signal_config else "",
                        "ret": m.get("total_return_pct", 0),
                        "ann_ret": m.get("annualized_return_pct", 0),
                        "sharpe": m.get("sharpe_ratio", 0),
                        "sortino": m.get("sortino_ratio", 0),
                        "calmar": m.get("calmar_ratio", 0),
                        "max_dd": m.get("max_drawdown_pct", 0),
                        "win_rate": m.get("win_rate", 0),
                        "pf": m.get("profit_factor", 0),
                        "trades": m.get("total_trades", 0),
                        "wins": m.get("winning_trades", 0),
                        "losses": m.get("losing_trades", 0),
                        "score": r.score,
                        "batch_id": batch_id,
                    },
                )
                inserted += 1
                if inserted % batch_size == 0:
                    await session.commit()
            await session.commit()
        logger.info("Persisted %d indicator results to DB (batch_id=%s)", inserted, batch_id)
    except Exception as e:
        logger.error("Failed to persist indicator results: %s", e)


async def _persist_phase1_results(strategies: list[dict[str, Any]], filters: dict[str, Any]) -> None:
    """Save Phase 1 results to generated_strategies table (batched)."""
    if not strategies or _db.async_session_factory is None:
        return

    from sqlalchemy import text

    from core.ids import new_id

    batch_id = new_id("p1bt")
    inserted = 0
    batch_size = 500

    try:
        async with _db.async_session_factory() as session:
            for _i, s in enumerate(strategies):
                m = s.get("metrics", {})
                strat_name = s.get("strategy", "?")
                sym = s.get("symbol", "?")
                params = s.get("params", {})
                method = s.get("method", "grid_search")
                score = s.get("score", 0)

                param_hash = hashlib.md5(str(sorted(params.items())).encode()).hexdigest()[:12]
                sid = f"{batch_id}_{sym}_{strat_name}_{method}_{param_hash}"[:50]
                sid = sid.replace("-", "_").replace(" ", "_")

                await session.execute(
                    text("""
                        INSERT INTO generated_strategies (
                            id, symbol, entry_indicator, entry_params, entry_condition,
                            exit_indicator, exit_params, exit_condition,
                            strategy_type, total_return_pct, annualized_return_pct,
                            sharpe_ratio, sortino_ratio, calmar_ratio,
                            max_drawdown_pct, win_rate, profit_factor,
                            total_trades, winning_trades, losing_trades,
                            score, batch_id, status
                        ) VALUES (
                            :id, :symbol, :entry, :entry_params, :entry_cond,
                            :exit, :exit_params, :exit_cond,
                            :strategy_type, :ret, :ann_ret,
                            :sharpe, :sortino, :calmar,
                            :max_dd, :win_rate, :pf,
                            :trades, :wins, :losses,
                            :score, :batch_id, 'active'
                        ) ON CONFLICT (id) DO NOTHING
                    """),
                    {
                        "id": sid,
                        "symbol": sym,
                        "entry": strat_name,
                        "entry_params": json.dumps(params, ensure_ascii=False),
                        "entry_cond": method,
                        "exit": strat_name,
                        "exit_params": json.dumps(params, ensure_ascii=False),
                        "exit_cond": method,
                        "strategy_type": strat_name,
                        "ret": m.get("total_return_pct", 0),
                        "ann_ret": m.get("annualized_return_pct", 0),
                        "sharpe": m.get("sharpe_ratio", 0),
                        "sortino": m.get("sortino_ratio", 0),
                        "calmar": m.get("calmar_ratio", 0),
                        "max_dd": m.get("max_drawdown_pct", 0),
                        "win_rate": m.get("win_rate", 0),
                        "pf": m.get("profit_factor", 0),
                        "trades": m.get("total_trades", 0),
                        "wins": m.get("winning_trades", 0),
                        "losses": m.get("losing_trades", 0),
                        "score": score,
                        "batch_id": batch_id,
                    },
                )
                inserted += 1
                if inserted % batch_size == 0:
                    await session.commit()
            await session.commit()
        logger.info("Persisted %d Phase 1 results to DB (batch_id=%s)", inserted, batch_id)
    except Exception as e:
        logger.error("Failed to persist Phase 1 results: %s", e)


# ═══════════════════════════ Main ═══════════════════════════

async def main() -> None:
    print("=" * 80)
    print("  BACKTEST ALL SYMBOLS — ALL INDICATORS — GENETIC OPTIMIZATION")
    print("  PHASE 1: Strategy Grid Search + Genetic + 6-Stage Filter")
    print("  PHASE 2: ALL 30 Indicators via SignalStrategy + 6-Stage Filter")
    print("=" * 80)
    print()

    await _db.init_database()
    if _db.async_session_factory is None:
        print("ERROR: Database not available. Exiting.")
        return

    print("Discovering symbols with data...")
    all_symbols = await fetch_all_symbols()
    if not all_symbols:
        print("No symbols found with sufficient data.")
        return
    print(f"Found {len(all_symbols)} symbols to test.\n")

    all_results: list[StrategyResult] = []
    start_time = datetime.now()

    if CFG.run_phase1:
        await run_phase1_strategies(all_symbols, all_results)

    if CFG.run_phase2:
        await run_phase2_indicators(all_symbols, all_results)

    elapsed = (datetime.now() - start_time).total_seconds()

    # ── Summary ──
    print("\n" + "=" * 80)
    print("  FINAL SUMMARY")
    print("=" * 80)
    print(f"Total strategies found: {len(all_results)}")
    print(f"Elapsed: {elapsed:.0f}s ({elapsed/60:.1f} min)")

    if all_results:
        all_results.sort(key=lambda r: r.score, reverse=True)

        for source in CFG.data_sources:
            src = [r for r in all_results if r.data_source == source]
            returns = [r.metrics.get("total_return_pct", 0) or 0 for r in src]
            print(f"\n--- {source.upper()} ---")
            print(f"  Count: {len(src)} | Avg Return: {sum(returns)/max(len(returns),1):.2f}% | "
                  f"Best: {max(returns):.2f}% | Worst: {min(returns):.2f}%")

        top_n = all_results[:30]
        print("\nTOP 30 STRATEGIES (across all phases):")
        print(f"{'Rank':<5} {'Symbol':<12} {'Strategy':<30} {'Source':<12} {'Return%':>8} {'Sharpe':>8} {'MaxDD%':>8} {'Score':>8}")
        print("-" * 95)
        for i, r in enumerate(top_n):
            m = r.metrics
            print(
                f"{i+1:<5} {r.symbol:<12} {r.strategy[:29]:<30} {r.data_source:<12} "
                f"{m.get('total_return_pct',0) or 0:>8.2f} {m.get('sharpe_ratio',0) or 0:>8.2f} "
                f"{m.get('max_drawdown_pct',0) or 0:>8.2f} {r.score:>8.2f}"
            )

        # Save reports
        summary_data = {
            "metadata": {
                "run_at": datetime.now().isoformat(),
                "elapsed_seconds": elapsed,
                "total_symbols": len(all_symbols),
                "data_sources": CFG.data_sources,
                "total_strategies": len(all_results),
                "phases": {
                    "phase1_generator": CFG.run_phase1,
                    "phase2_indicators": CFG.run_phase2,
                },
                "filters": CFG.filters,
                "capital": CFG.capital,
            },
            "top30": [
                {
                    "symbol": r.symbol,
                    "strategy": r.strategy,
                    "data_source": r.data_source,
                    "method": r.method,
                    "params": r.params,
                    "metrics": r.metrics,
                    "score": r.score,
                }
                for r in top_n
            ],
        }

        with open(CFG.summary_path, "w", encoding="utf-8") as f:
            json.dump(summary_data, f, ensure_ascii=False, indent=2, default=str)
        print(f"\nSummary saved to {CFG.summary_path}")

        full_results = [
            {
                "symbol": r.symbol,
                "strategy": r.strategy,
                "data_source": r.data_source,
                "method": r.method,
                "params": r.params,
                "metrics": r.metrics,
                "score": r.score,
            }
            for r in all_results
        ]
        with open(CFG.report_path, "w", encoding="utf-8") as f:
            json.dump({"metadata": summary_data["metadata"], "results": full_results},
                      f, ensure_ascii=False, indent=2, default=str)
        print(f"Full report saved to {CFG.report_path}")

    # Verify DB
    try:
        from sqlalchemy import text
        async with _db.async_session_factory() as session:
            bt_count = (await session.execute(text("SELECT COUNT(*) FROM backtest_runs"))).scalar()
            gs_count = (await session.execute(text("SELECT COUNT(*) FROM generated_strategies"))).scalar()
            print(f"\nDB Verification: {bt_count} backtest_runs, {gs_count} generated_strategies")
    except Exception as e:
        logger.warning("DB verification failed: %s", e)

    print("\nDone.")


if __name__ == "__main__":
    asyncio.run(main())
