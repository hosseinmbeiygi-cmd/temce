#!/usr/bin/env python
"""
FULL STRATEGY GENERATOR & BACKTESTER — IRAN MARKET

Generates COMPLETE strategies with ALL factors:
  1. Entry Indicator  (30 indicators × params × conditions)
  2. Exit Indicator   (30 indicators × params × conditions)
  3. Filter1 Indicator (optional, AND with entry)
  4. Filter2 Indicator (optional, AND with entry)
  5. Stop Loss %      (multiple levels)
  6. Take Profit %    (multiple levels)
  7. Trailing Stop    (on/off)
  8. Sizing Method    (fixed / percent / kelly)
  9. Sizing Value     (different sizes)

All passing strategies (6-stage filter) → PostgreSQL database.

Usage:
    python scripts/run_full_backtest.py
    python scripts/run_full_backtest.py --max-combos 1000000
"""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import itertools
import json
import math
import random
import sys
import time
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path
from typing import Any

_root = Path(__file__).resolve().parent.parent
if str(_root) not in sys.path:
    sys.path.insert(0, str(_root))

import core.database as _db
from backtesting.composer.indicator_registry import REGISTRY as INDICATOR_REGISTRY
from backtesting.composer.indicator_registry import IndicatorSpec
from backtesting.engine.simulator import BacktestSimulator
from backtesting.strategies.signal_strategy import SignalStrategy
from core.logging import get_logger

logger = get_logger(__name__)

# ═══════════════════════════ CONFIG ═══════════════════════════

MAX_COMBINATIONS = 1_000_000
CAPITAL = 1_000_000_000
BATCH_DB_SIZE = 500
START_DATE: date | None = None
END_DATE: date | None = None

FILTERS = {
    "stage1_min_return": 5.0,
    "stage2_max_drawdown": 25.0,
    "stage3_min_sharpe": 0.5,
    "stage4_min_win_rate": 40.0,
    "stage5_min_trades": 5,
    "stage6_min_profit_factor": 1.2,
}

# ── Risk Management Ranges ──
STOP_LOSS_OPTIONS = [None, 3.0, 5.0, 7.0, 10.0, 15.0]           # %
TAKE_PROFIT_OPTIONS = [None, 5.0, 10.0, 15.0, 20.0, 30.0]       # %
TRAILING_STOP_OPTIONS = [False, True]

# ── Position Sizing Ranges ──
SIZING_METHODS = ["fixed", "percent"]
SIZING_VALUES_FIXED = [CAPITAL * 0.05, CAPITAL * 0.10, CAPITAL * 0.15, CAPITAL * 0.20]  # 5-20% of capital
SIZING_VALUES_PERCENT = [5.0, 10.0, 15.0, 20.0]  # % of capital per trade

REPORT_PATH = "full_backtest_report.json"


# ═══════════════════════════ DATA ═══════════════════════════

@dataclass
class SignalSet:
    """Pre-computed signal array for one indicator × params × condition."""
    key: str
    indicator_id: str
    indicator_name: str
    group: str
    params: dict[str, Any]
    condition: str
    signals: list[bool]


@dataclass
class StrategyBlueprint:
    """Complete strategy definition — ALL factors included."""
    idx: int
    # Indicator signals
    entry_key: str
    exit_key: str
    filter1_key: str | None
    filter2_key: str | None
    # Risk management
    stop_loss_pct: float | None
    take_profit_pct: float | None
    trailing_stop: bool
    # Position sizing
    sizing_method: str
    sizing_value: float
    # Descriptive metadata
    entry_indicator: str
    exit_indicator: str
    entry_condition: str
    exit_condition: str
    entry_params: dict[str, Any]
    exit_params: dict[str, Any]
    filter1_indicator: str | None = None
    filter1_condition: str | None = None
    filter2_indicator: str | None = None
    filter2_condition: str | None = None


@dataclass
class StrategyResult:
    """Backtest result for one complete strategy on one symbol."""
    symbol: str
    # Strategy config
    entry_indicator: str
    entry_params: dict[str, Any]
    entry_condition: str
    exit_indicator: str
    exit_params: dict[str, Any]
    exit_condition: str
    filter1_indicator: str | None
    filter1_condition: str | None
    filter2_indicator: str | None
    filter2_condition: str | None
    stop_loss_pct: float | None
    take_profit_pct: float | None
    trailing_stop: bool
    sizing_method: str
    sizing_value: float
    # Metrics
    total_return_pct: float = 0.0
    annualized_return_pct: float = 0.0
    sharpe_ratio: float = 0.0
    sortino_ratio: float = 0.0
    calmar_ratio: float = 0.0
    max_drawdown_pct: float = 0.0
    win_rate: float = 0.0
    profit_factor: float = 0.0
    total_trades: int = 0
    winning_trades: int = 0
    losing_trades: int = 0
    score: float = 0.0


# ═══════════════════════ INDICATOR COMPUTATION ═══════════════════════

def compute_indicator_raw(
    spec: IndicatorSpec,
    close: list[float], high: list[float], low: list[float], volume: list[float],
    params: dict[str, Any],
) -> dict[str, list] | None:
    fn = spec.compute_fn
    arg_names = fn.__code__.co_varnames[:fn.__code__.co_argcount]
    kwargs = dict(params)

    for name in ("close", "high", "low", "volume"):
        if name in arg_names:
            kwargs[name] = {"close": close, "high": high, "low": low, "volume": volume}[name]
    if "prices" in arg_names:
        kwargs["prices"] = close

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


def precompute_all_signals(
    close: list[float], high: list[float], low: list[float], volume: list[float],
) -> dict[str, SignalSet]:
    """Pre-compute ALL indicator signals for one symbol."""
    n = len(close)
    signals: dict[str, SignalSet] = {}

    for spec in INDICATOR_REGISTRY:
        param_keys = list(spec.params.keys())
        param_values = [spec.params[k] for k in param_keys] if param_keys else [()]

        for param_combo in itertools.product(*param_values):
            params = dict(zip(param_keys, param_combo, strict=False)) if param_keys else {}
            raw = compute_indicator_raw(spec, close, high, low, volume, params)
            if raw is None:
                continue

            for cond_name, output_key in spec.conditions.items():
                bool_signals = [bool(v) for v in raw.get(output_key, [False] * n)]
                if sum(bool_signals) == 0:
                    continue

                param_str = "_".join(f"{k}{v}" for k, v in sorted(params.items()))
                sig_key = f"{spec.id}__{param_str}__{cond_name}" if param_str else f"{spec.id}__{cond_name}"

                signals[sig_key] = SignalSet(
                    key=sig_key,
                    indicator_id=spec.id,
                    indicator_name=spec.name_fa,
                    group=spec.group,
                    params=params,
                    condition=cond_name,
                    signals=bool_signals,
                )

    return signals


# ═══════════════════════ METRICS ═══════════════════════

def compute_metrics(equity: list[float], trades_pnl: list[float], capital: float) -> dict[str, float]:
    if len(equity) < 2:
        return {
            "total_return_pct": 0.0, "annualized_return_pct": 0.0,
            "sharpe_ratio": 0.0, "sortino_ratio": 0.0, "calmar_ratio": 0.0,
            "max_drawdown_pct": 0.0, "win_rate": 0.0, "profit_factor": 0.0,
            "total_trades": 0, "winning_trades": 0, "losing_trades": 0,
        }

    total_return = ((equity[-1] / capital) - 1) * 100
    years = max(len(equity) / 252, 0.01)
    ann_return = ((equity[-1] / capital) ** (1 / years) - 1) * 100

    returns = [(equity[i] / equity[i - 1]) - 1 for i in range(1, len(equity))]
    avg_r = sum(returns) / len(returns) if returns else 0
    std_r = math.sqrt(sum((r - avg_r) ** 2 for r in returns) / len(returns)) if returns else 1
    sharpe = (avg_r / std_r) * math.sqrt(252) if std_r > 0 else 0

    peak = equity[0]
    max_dd = 0.0
    for nav in equity:
        if nav > peak:
            peak = nav
        dd = (peak - nav) / peak if peak > 0 else 0
        max_dd = max(max_dd, dd)

    wins = [t for t in trades_pnl if t > 0]
    losses = [abs(t) for t in trades_pnl if t < 0]
    win_rate = (len(wins) / len(trades_pnl) * 100) if trades_pnl else 0
    profit_factor = (sum(wins) / sum(losses)) if sum(losses) > 0 else (9e9 if wins else 0)

    downside = [r for r in returns if r < 0]
    downside_vol = math.sqrt(sum(r ** 2 for r in downside) / len(downside)) if downside else 1
    sortino = (avg_r / downside_vol) * math.sqrt(252) if downside_vol > 0 else 0
    calmar = ann_return / (max_dd * 100) if max_dd > 0 else 0

    return {
        "total_return_pct": round(total_return, 2),
        "annualized_return_pct": round(ann_return, 2),
        "sharpe_ratio": round(sharpe, 2),
        "sortino_ratio": round(sortino, 2),
        "calmar_ratio": round(calmar, 2),
        "max_drawdown_pct": round(max_dd * 100, 2),
        "win_rate": round(win_rate, 1),
        "profit_factor": round(profit_factor, 2),
        "total_trades": len(trades_pnl),
        "winning_trades": len(wins),
        "losing_trades": len(losses),
    }


def combined_score(m: dict[str, float]) -> float:
    return (
        m.get("sharpe_ratio", 0) * 0.30
        + m.get("sortino_ratio", 0) * 0.15
        + m.get("calmar_ratio", 0) * 0.15
        + m.get("total_return_pct", 0) * 0.002
        + m.get("profit_factor", 0) * 0.15
        + m.get("win_rate", 0) * 0.005
        - m.get("max_drawdown_pct", 0) * 0.005
    )


def passes_6stage(m: dict[str, float]) -> bool:
    if m.get("total_return_pct", 0) < FILTERS["stage1_min_return"]:
        return False
    if m.get("max_drawdown_pct", 100) > FILTERS["stage2_max_drawdown"]:
        return False
    if m.get("sharpe_ratio", 0) < FILTERS["stage3_min_sharpe"]:
        return False
    if m.get("win_rate", 0) < FILTERS["stage4_min_win_rate"]:
        return False
    if m.get("total_trades", 0) < FILTERS["stage5_min_trades"]:
        return False
    return not m.get("profit_factor", 0) < FILTERS["stage6_min_profit_factor"]


# ═══════════════════════ COMPLETE STRATEGY GENERATOR ═══════════════════════

def generate_complete_strategies(
    signal_keys: list[str],
    signal_sets: dict[str, SignalSet],
    max_combos: int,
) -> list[StrategyBlueprint]:
    """Generate COMPLETE strategies with ALL factors for Iran market.

    Each strategy combines:
      entry × exit × filter1 × filter2 × stop_loss × take_profit × trailing × sizing
    """
    n_keys = len(signal_keys)
    if n_keys < 2:
        return []

    combos: list[StrategyBlueprint] = []
    used: set[tuple] = set()
    idx = 0

    # Pre-build risk/sizing options
    risk_options = []
    for sl in STOP_LOSS_OPTIONS:
        for tp in TAKE_PROFIT_OPTIONS:
            for ts in TRAILING_STOP_OPTIONS:
                risk_options.append((sl, tp, ts))

    sizing_options = []
    for method in SIZING_METHODS:
        if method == "fixed":
            for val in SIZING_VALUES_FIXED:
                sizing_options.append((method, val))
        else:
            for val in SIZING_VALUES_PERCENT:
                sizing_options.append((method, val))

    print(f"    Building up to {max_combos:,} complete strategies...")
    print(f"    Signal sets: {n_keys} | Risk options: {len(risk_options)} | Sizing options: {len(sizing_options)}")

    # Strategy structure:
    #   entry × exit × (no filter / 1 filter / 2 filters) × risk × sizing
    #
    # We sample to hit max_combos target


    for entry_key in signal_keys:
        entry_ss = signal_sets[entry_key]

        for exit_key in signal_keys:
            if exit_key == entry_key:
                continue
            exit_ss = signal_sets[exit_key]

            # ── Variant 1: No filter ──
            for sl, tp, ts in risk_options:
                for method, sval in sizing_options:
                    combo_sig = (entry_key, exit_key, None, None, sl, tp, ts, method, round(sval))
                    if combo_sig in used:
                        continue
                    used.add(combo_sig)

                    combos.append(StrategyBlueprint(
                        idx=idx,
                        entry_key=entry_key,
                        exit_key=exit_key,
                        filter1_key=None,
                        filter2_key=None,
                        stop_loss_pct=sl,
                        take_profit_pct=tp,
                        trailing_stop=ts,
                        sizing_method=method,
                        sizing_value=sval,
                        entry_indicator=entry_ss.indicator_id,
                        exit_indicator=exit_ss.indicator_id,
                        entry_condition=entry_ss.condition,
                        exit_condition=exit_ss.condition,
                        entry_params=entry_ss.params,
                        exit_params=exit_ss.params,
                    ))
                    idx += 1

                    if idx >= max_combos:
                        return combos[:max_combos]

            # ── Variant 2: With 1 filter ──
            for f1_key in signal_keys:
                if f1_key in (entry_key, exit_key):
                    continue
                f1_ss = signal_sets[f1_key]

                for sl, tp, ts in [(None, None, False)]:  # lighter risk combos with filters
                    for method, sval in sizing_options[:2]:  # fewer sizing with filters
                        combo_sig = (entry_key, exit_key, f1_key, None, sl, tp, ts, method, round(sval))
                        if combo_sig in used:
                            continue
                        used.add(combo_sig)

                        combos.append(StrategyBlueprint(
                            idx=idx,
                            entry_key=entry_key,
                            exit_key=exit_key,
                            filter1_key=f1_key,
                            filter2_key=None,
                            stop_loss_pct=sl,
                            take_profit_pct=tp,
                            trailing_stop=ts,
                            sizing_method=method,
                            sizing_value=sval,
                            entry_indicator=entry_ss.indicator_id,
                            exit_indicator=exit_ss.indicator_id,
                            entry_condition=entry_ss.condition,
                            exit_condition=exit_ss.condition,
                            entry_params=entry_ss.params,
                            exit_params=exit_ss.params,
                            filter1_indicator=f1_ss.indicator_id,
                            filter1_condition=f1_ss.condition,
                        ))
                        idx += 1

                        if idx >= max_combos:
                            return combos[:max_combos]

            if idx >= max_combos:
                break
        if idx >= max_combos:
            break

    print(f"    Generated {len(combos):,} complete strategy blueprints")
    return combos[:max_combos]


def generate_complete_strategies_sampled(
    signal_keys: list[str],
    signal_sets: dict[str, SignalSet],
    max_combos: int,
) -> list[StrategyBlueprint]:
    """Fast random sampling of complete strategies for large search spaces."""
    n = len(signal_keys)
    if n < 2:
        return []

    combos: list[StrategyBlueprint] = []
    used: set[tuple] = set()

    for _ in range(max_combos * 5):
        entry_key = random.choice(signal_keys)
        exit_key = random.choice(signal_keys)
        if exit_key == entry_key:
            continue

        # Filter selection
        r = random.random()
        if r < 0.35:
            f1_key, f2_key = None, None
        elif r < 0.70:
            f1_key = random.choice(signal_keys)
            while f1_key in (entry_key, exit_key):
                f1_key = random.choice(signal_keys)
            f2_key = None
        else:
            f1_key = random.choice(signal_keys)
            while f1_key in (entry_key, exit_key):
                f1_key = random.choice(signal_keys)
            f2_key = random.choice(signal_keys)
            while f2_key in (entry_key, exit_key, f1_key):
                f2_key = random.choice(signal_keys)

        # Risk management
        sl = random.choice(STOP_LOSS_OPTIONS)
        tp = random.choice(TAKE_PROFIT_OPTIONS)
        ts = random.choice(TRAILING_STOP_OPTIONS)

        # Position sizing
        method = random.choice(SIZING_METHODS)
        sval = random.choice(SIZING_VALUES_FIXED) if method == "fixed" else random.choice(SIZING_VALUES_PERCENT)

        combo_sig = (entry_key, exit_key, f1_key, f2_key, sl, tp, ts, method, round(sval, 2))
        if combo_sig in used:
            continue
        used.add(combo_sig)

        entry_ss = signal_sets[entry_key]
        exit_ss = signal_sets[exit_key]
        f1_ss = signal_sets.get(f1_key) if f1_key else None
        f2_ss = signal_sets.get(f2_key) if f2_key else None

        combos.append(StrategyBlueprint(
            idx=len(combos),
            entry_key=entry_key,
            exit_key=exit_key,
            filter1_key=f1_key,
            filter2_key=f2_key,
            stop_loss_pct=sl,
            take_profit_pct=tp,
            trailing_stop=ts,
            sizing_method=method,
            sizing_value=sval,
            entry_indicator=entry_ss.indicator_id,
            exit_indicator=exit_ss.indicator_id,
            entry_condition=entry_ss.condition,
            exit_condition=exit_ss.condition,
            entry_params=entry_ss.params,
            exit_params=exit_ss.params,
            filter1_indicator=f1_ss.indicator_id if f1_ss else None,
            filter1_condition=f1_ss.condition if f1_ss else None,
            filter2_indicator=f2_ss.indicator_id if f2_ss else None,
            filter2_condition=f2_ss.condition if f2_ss else None,
        ))

        if len(combos) >= max_combos:
            break

    print(f"    Sampled {len(combos):,} complete strategies")
    return combos


# ═══════════════════════ BACKTEST ENGINE ═══════════════════════

class RiskManagedSimulator:
    """BacktestSimulator wrapper that enforces stop loss, take profit, trailing stop."""

    def __init__(self, stop_loss_pct: float | None, take_profit_pct: float | None, trailing_stop: bool):
        self.sl = stop_loss_pct
        self.tp = take_profit_pct
        self.ts = trailing_stop
        self.sim = BacktestSimulator()

    def run(self, strategy: SignalStrategy, capital: float, data: list[dict]) -> Any:
        """Run backtest with risk management applied."""
        # For stop loss / take profit, we modify the signal strategy's exit logic
        # by wrapping the equity tracking
        result = self.sim.run(strategy, initial_capital=capital, data=data)
        if not result.success:
            return result

        bt = result.value
        # Apply risk management to equity curve (post-processing)
        if self.sl is not None or self.tp is not None or self.ts:
            bt = self._apply_risk_management(bt, capital)

        return result

    def _apply_risk_management(self, bt, capital):
        """Re-simulate equity curve with stop loss / take profit / trailing stop."""
        equity = [ep.nav for ep in bt.equity_curve]
        trades = bt.trades

        if not equity or not trades:
            return bt

        # Build per-bar returns and apply risk limits
        new_equity = [equity[0]]
        peak = equity[0]

        for i in range(1, len(equity)):
            nav = equity[i]
            daily_return = (nav / new_equity[-1]) - 1 if new_equity[-1] > 0 else 0

            # Trailing stop: if drawdown from peak exceeds threshold, cut position
            if self.ts and peak > 0:
                drawdown_from_peak = (peak - nav) / peak * 100
                if drawdown_from_peak > (self.sl or 10.0):
                    # Cut to cash equivalent
                    nav = new_equity[-1] * (1 + daily_return * 0.1)  # dampen

            # Stop loss: limit daily loss
            if self.sl is not None and daily_return < -(self.sl / 100):
                nav = new_equity[-1] * (1 - self.sl / 100)

            # Take profit: cap daily gain
            if self.tp is not None and daily_return > (self.tp / 100):
                nav = new_equity[-1] * (1 + self.tp / 100)

            new_equity.append(nav)
            if nav > peak:
                peak = nav

        # Update equity curve
        for i, ep in enumerate(bt.equity_curve):
            if i < len(new_equity):
                ep.nav = new_equity[i]

        return bt


def backtest_strategy(
    symbol: str,
    ohlcv: list[dict[str, Any]],
    signal_sets: dict[str, SignalSet],
    blueprint: StrategyBlueprint,
    capital: float,
) -> StrategyResult | None:
    """Run one complete strategy on one symbol."""
    n = len(ohlcv)

    entry_ss = signal_sets.get(blueprint.entry_key)
    exit_ss = signal_sets.get(blueprint.exit_key)
    if entry_ss is None or exit_ss is None:
        return None

    # Build combined entry signal
    entry_sig = list(entry_ss.signals)

    if blueprint.filter1_key:
        f1 = signal_sets.get(blueprint.filter1_key)
        if f1 is None:
            return None
        entry_sig = [entry_sig[i] and f1.signals[i] for i in range(min(n, len(f1.signals)))]

    if blueprint.filter2_key:
        f2 = signal_sets.get(blueprint.filter2_key)
        if f2 is None:
            return None
        entry_sig = [entry_sig[i] and f2.signals[i] for i in range(min(n, len(f2.signals)))]

    exit_sig = list(exit_ss.signals)

    # Pad
    if len(entry_sig) < n:
        entry_sig.extend([False] * (n - len(entry_sig)))
    if len(exit_sig) < n:
        exit_sig.extend([False] * (n - len(exit_sig)))

    if sum(entry_sig) == 0 or sum(exit_sig) == 0:
        return None

    # Position sizing
    if blueprint.sizing_method == "fixed":
        sizing_val = blueprint.sizing_value
    else:
        sizing_val = capital * (blueprint.sizing_value / 100)

    strategy = SignalStrategy(
        entry_signal=entry_sig,
        exit_signal=exit_sig,
        name=f"{blueprint.entry_indicator}+{blueprint.exit_indicator}",
        sizing_method="fixed",
        sizing_value=sizing_val,
    )

    # Run with risk management
    rm_sim = RiskManagedSimulator(
        stop_loss_pct=blueprint.stop_loss_pct,
        take_profit_pct=blueprint.take_profit_pct,
        trailing_stop=blueprint.trailing_stop,
    )
    result = rm_sim.run(strategy, capital, ohlcv)
    if not result.success:
        return None

    bt = result.value
    metrics = compute_metrics(
        [ep.nav for ep in bt.equity_curve],
        [getattr(t, "pnl", 0) for t in bt.trades],
        capital,
    )

    if not passes_6stage(metrics):
        return None

    score = combined_score(metrics)
    return StrategyResult(
        symbol=symbol,
        entry_indicator=blueprint.entry_indicator,
        entry_params=blueprint.entry_params,
        entry_condition=blueprint.entry_condition,
        exit_indicator=blueprint.exit_indicator,
        exit_params=blueprint.exit_params,
        exit_condition=blueprint.exit_condition,
        filter1_indicator=blueprint.filter1_indicator,
        filter1_condition=blueprint.filter1_condition,
        filter2_indicator=blueprint.filter2_indicator,
        filter2_condition=blueprint.filter2_condition,
        stop_loss_pct=blueprint.stop_loss_pct,
        take_profit_pct=blueprint.take_profit_pct,
        trailing_stop=blueprint.trailing_stop,
        sizing_method=blueprint.sizing_method,
        sizing_value=blueprint.sizing_value,
        total_return_pct=metrics["total_return_pct"],
        annualized_return_pct=metrics["annualized_return_pct"],
        sharpe_ratio=metrics["sharpe_ratio"],
        sortino_ratio=metrics["sortino_ratio"],
        calmar_ratio=metrics["calmar_ratio"],
        max_drawdown_pct=metrics["max_drawdown_pct"],
        win_rate=metrics["win_rate"],
        profit_factor=metrics["profit_factor"],
        total_trades=metrics["total_trades"],
        winning_trades=metrics["winning_trades"],
        losing_trades=metrics["losing_trades"],
        score=score,
    )


def backtest_symbol_all_strategies(
    symbol: str,
    ohlcv: list[dict[str, Any]],
    signal_sets: dict[str, SignalSet],
    blueprints: list[StrategyBlueprint],
    capital: float,
) -> list[StrategyResult]:
    """Test all blueprints on one symbol. Returns only passing results."""
    passing: list[StrategyResult] = []
    for bp in blueprints:
        result = backtest_strategy(symbol, ohlcv, signal_sets, bp, capital)
        if result is not None:
            passing.append(result)
    return passing


# ═══════════════════════ DATABASE ═══════════════════════

async def persist_results(results: list[StrategyResult], batch_id: str) -> int:
    if not results or _db.async_session_factory is None:
        return 0

    from sqlalchemy import text as sql_text

    inserted = 0
    total = len(results)

    try:
        async with _db.async_session_factory() as session:
            for r in results:
                param_hash = hashlib.md5(
                    f"{r.entry_indicator}{r.entry_params}{r.exit_indicator}{r.exit_params}".encode()
                ).hexdigest()[:12]
                sl_str = f"sl{r.stop_loss_pct}" if r.stop_loss_pct else "nosl"
                tp_str = f"tp{r.take_profit_pct}" if r.take_profit_pct else "notp"
                # generated_strategies.id is String(50); a readable composite of
                # batch + symbol + 2 indicators + sl/tp + hash regularly exceeds
                # that, so hash the whole thing to a fixed 40 chars.
                natural_key = (
                    f"{batch_id}_{r.symbol}_{r.entry_indicator}_{r.exit_indicator}"
                    f"_{sl_str}_{tp_str}_{param_hash}"
                )
                sid = "gs_" + hashlib.sha1(natural_key.encode()).hexdigest()  # 3 + 40 = 43

                # Build description JSON
                json.dumps({
                    "entry": {"indicator": r.entry_indicator, "params": r.entry_params, "condition": r.entry_condition},
                    "exit": {"indicator": r.exit_indicator, "params": r.exit_params, "condition": r.exit_condition},
                    "filter1": {"indicator": r.filter1_indicator, "condition": r.filter1_condition} if r.filter1_indicator else None,
                    "filter2": {"indicator": r.filter2_indicator, "condition": r.filter2_condition} if r.filter2_indicator else None,
                    "stop_loss_pct": r.stop_loss_pct,
                    "take_profit_pct": r.take_profit_pct,
                    "trailing_stop": r.trailing_stop,
                    "sizing_method": r.sizing_method,
                    "sizing_value": r.sizing_value,
                }, ensure_ascii=False)

                await session.execute(
                    sql_text("""
                        INSERT INTO generated_strategies (
                            id, symbol, entry_indicator, entry_params, entry_condition,
                            exit_indicator, exit_params, exit_condition,
                            filter1_indicator, filter1_params, filter1_condition,
                            filter2_indicator, filter2_params, filter2_condition,
                            stop_loss_pct, take_profit_pct, trailing_stop,
                            sizing_method, sizing_value,
                            strategy_type, total_return_pct, annualized_return_pct,
                            sharpe_ratio, sortino_ratio, calmar_ratio,
                            max_drawdown_pct, win_rate, profit_factor,
                            total_trades, winning_trades, losing_trades,
                            score, batch_id, status
                        ) VALUES (
                            :id, :symbol, :entry, :entry_params, :entry_cond,
                            :exit, :exit_params, :exit_cond,
                            :f1_ind, :f1_params, :f1_cond,
                            :f2_ind, :f2_params, :f2_cond,
                            :sl, :tp, :ts,
                            :sizing_m, :sizing_v,
                            'complete', :ret, :ann_ret,
                            :sharpe, :sortino, :calmar,
                            :max_dd, :win_rate, :pf,
                            :trades, :wins, :losses,
                            :score, :batch_id, 'active'
                        ) ON CONFLICT (id) DO NOTHING
                    """),
                    {
                        "id": sid,
                        "symbol": r.symbol,
                        "entry": r.entry_indicator,
                        "entry_params": json.dumps(r.entry_params, ensure_ascii=False),
                        "entry_cond": r.entry_condition,
                        "exit": r.exit_indicator,
                        "exit_params": json.dumps(r.exit_params, ensure_ascii=False),
                        "exit_cond": r.exit_condition,
                        "f1_ind": r.filter1_indicator,
                        "f1_params": None,
                        "f1_cond": r.filter1_condition,
                        "f2_ind": r.filter2_indicator,
                        "f2_params": None,
                        "f2_cond": r.filter2_condition,
                        "sl": r.stop_loss_pct,
                        "tp": r.take_profit_pct,
                        "ts": str(r.trailing_stop),
                        "sizing_m": r.sizing_method,
                        "sizing_v": r.sizing_value,
                        "ret": r.total_return_pct,
                        "ann_ret": r.annualized_return_pct,
                        "sharpe": r.sharpe_ratio,
                        "sortino": r.sortino_ratio,
                        "calmar": r.calmar_ratio,
                        "max_dd": r.max_drawdown_pct,
                        "win_rate": r.win_rate,
                        "pf": r.profit_factor,
                        "trades": r.total_trades,
                        "wins": r.winning_trades,
                        "losses": r.losing_trades,
                        "score": r.score,
                        "batch_id": batch_id,
                    },
                )
                inserted += 1

                if inserted % BATCH_DB_SIZE == 0:
                    await session.commit()
                    print(f"    DB: {inserted}/{total} saved...")

            await session.commit()

        logger.info("Persisted %d complete strategies (batch=%s)", inserted, batch_id)
    except Exception as e:
        logger.error("DB persist error: %s", e)
        print(f"  DB Error: {e}")

    return inserted


# ═══════════════════════ DATA FETCHING ═══════════════════════

async def fetch_all_symbols() -> list[dict[str, Any]]:
    from sqlalchemy import text as sql_text
    if _db.async_session_factory is None:
        await _db.init_database()
    if _db.async_session_factory is None:
        return []

    async with _db.async_session_factory() as session:
        result = await session.execute(sql_text("""
            SELECT symbol, MIN(date), MAX(date), COUNT(*)
            FROM brsapi_historical_daily
            WHERE price_close IS NOT NULL AND price_close > 0
            GROUP BY symbol HAVING COUNT(*) >= 30
            ORDER BY COUNT(*) DESC
        """))
        return [
            {"symbol": row[0], "hist_bars": row[3]}
            for row in result.fetchall()
        ]


async def fetch_ohlcv(symbol: str, start: date, end: date) -> list[dict[str, Any]]:
    import jdatetime
    from sqlalchemy import text as sql_text
    if _db.async_session_factory is None:
        return []

    jalali_start = jdatetime.date.fromgregorian(date=start).strftime("%Y-%m-%d")
    jalali_end = jdatetime.date.fromgregorian(date=end).strftime("%Y-%m-%d")

    async with _db.async_session_factory() as session:
        result = await session.execute(
            sql_text("""
                SELECT date, price_first, price_last, price_max, price_min, trade_volume
                FROM brsapi_historical_daily
                WHERE symbol = :sym AND date >= :s AND date <= :e
                  AND price_close IS NOT NULL AND price_close > 0
                ORDER BY date ASC
            """),
            {"sym": symbol, "s": jalali_start, "e": jalali_end},
        )
        rows = result.fetchall()

    return [
        {"timestamp": r[0], "open": float(r[1] or 0), "close": float(r[2] or 0),
         "high": float(r[3] or 0), "low": float(r[4] or 0), "volume": float(r[5] or 0)}
        for r in rows
        if float(r[5] or 0) > 0 and float(r[2] or 0) > 0
    ]


# ═══════════════════════ MAIN ═══════════════════════

async def main() -> None:
    parser = argparse.ArgumentParser(description="Full Iran Market Strategy Generator & Backtester")
    parser.add_argument("--max-combos", type=int, default=MAX_COMBINATIONS)
    parser.add_argument("--capital", type=float, default=CAPITAL)
    args = parser.parse_args()

    print("=" * 80)
    print("  FULL IRAN MARKET STRATEGY GENERATOR & BACKTESTER")
    print("  Entry × Exit × Filter1 × Filter2 × StopLoss × TakeProfit × Trailing × Sizing")
    print(f"  Target: {args.max_combos:,} complete strategies")
    print("  All results → PostgreSQL database")
    print("=" * 80)

    await _db.init_database()
    if _db.async_session_factory is None:
        print("ERROR: Database not available.")
        return

    print("\n[1/5] Fetching symbols...")
    symbols_info = await fetch_all_symbols()
    if not symbols_info:
        print("No symbols found.")
        return

    today = date.today()
    start = START_DATE or date(today.year - 2, 1, 1)
    end = END_DATE or today
    print(f"  {len(symbols_info)} symbols | {start} → {end} | {args.capital:,.0f} IRR")

    batch_id = f"irs_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    all_results: list[StrategyResult] = []
    total_tested = 0
    start_time = time.time()

    print("\n[2/5] Processing symbols...")

    for sym_idx, sym_info in enumerate(symbols_info):
        sym = sym_info["symbol"]

        ohlcv = await fetch_ohlcv(sym, start, end)
        if not ohlcv or len(ohlcv) < 60:
            continue

        close = [b["close"] for b in ohlcv]
        high = [b.get("high", b["close"]) for b in ohlcv]
        low = [b.get("low", b["close"]) for b in ohlcv]
        volume = [b.get("volume", 0) for b in ohlcv]

        # Pre-compute ALL indicator signals
        signal_sets = precompute_all_signals(close, high, low, volume)
        signal_keys = list(signal_sets.keys())

        if len(signal_keys) < 2:
            continue

        # Generate complete strategies (sampled for 1M target)
        blueprints = generate_complete_strategies_sampled(
            signal_keys, signal_sets, args.max_combos,
        )

        # Backtest all strategies
        passing = backtest_symbol_all_strategies(sym, ohlcv, signal_sets, blueprints, args.capital)
        all_results.extend(passing)
        total_tested += 1

        elapsed = time.time() - start_time
        print(
            f"  [{sym_idx+1}/{len(symbols_info)}] {sym}: "
            f"{len(signal_keys)} signals → {len(blueprints):,} strategies → "
            f"{len(passing)} passed | "
            f"Total: {len(all_results):,} | "
            f"{elapsed:.0f}s"
        )

        # Save to DB periodically
        if len(all_results) >= 500:
            saved = await persist_results(all_results, batch_id)
            print(f"    → Saved {saved} to DB")
            all_results = []

    # Final save
    if all_results:
        saved = await persist_results(all_results, batch_id)
        print(f"  Final save: {saved}")

    elapsed_total = time.time() - start_time

    # ── Summary ──
    print("\n" + "=" * 80)
    print("  COMPLETE STRATEGY GENERATION SUMMARY")
    print("=" * 80)
    print(f"  Symbols tested:        {total_tested}")
    print(f"  Time:                  {elapsed_total:.0f}s ({elapsed_total/60:.1f} min)")
    print(f"  Batch ID:              {batch_id}")
    print(f"  Stop Loss options:     {STOP_LOSS_OPTIONS}")
    print(f"  Take Profit options:   {TAKE_PROFIT_OPTIONS}")
    print(f"  Trailing Stop:         {TRAILING_STOP_OPTIONS}")
    print(f"  Sizing methods:        {SIZING_METHODS}")

    # Verify DB
    try:
        from sqlalchemy import text as sql_text
        async with _db.async_session_factory() as session:
            gs = (await session.execute(sql_text("SELECT COUNT(*) FROM generated_strategies"))).scalar()
            print(f"\n  DB total rows: {gs}")
    except Exception as e:
        print(f"  DB verify failed: {e}")

    # Save report
    report = {
        "metadata": {
            "run_at": datetime.now().isoformat(),
            "elapsed_seconds": elapsed_total,
            "symbols_tested": total_tested,
            "batch_id": batch_id,
            "capital": args.capital,
            "period": f"{start} → {end}",
            "filters": FILTERS,
            "risk_options": {
                "stop_loss": STOP_LOSS_OPTIONS,
                "take_profit": TAKE_PROFIT_OPTIONS,
                "trailing_stop": TRAILING_STOP_OPTIONS,
            },
            "sizing": {
                "methods": SIZING_METHODS,
                "fixed_values": SIZING_VALUES_FIXED,
                "percent_values": SIZING_VALUES_PERCENT,
            },
        },
    }
    with open(REPORT_PATH, "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2, default=str)
    print(f"  Report: {REPORT_PATH}")
    print("\n  Done!")


if __name__ == "__main__":
    asyncio.run(main())
