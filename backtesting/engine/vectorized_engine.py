"""
Vectorized Backtest Engine — موتور بک‌تست برداری فوق‌سریع
=========================================================

برای اسکرین سریع استراتژی‌ها روی دیتافریم‌های تاریخی — بدون حلقه،
با محاسبات برداری pandas. مناسب برای استراتژی‌های ساده (تقاطع MA، RSI، ...).

ویژگی‌ها:
  * `run_strategy(strategy_func, data)` — اجرای استراتژی با یک بار محاسبه
  * `calculate_metrics(returns)` — شارپ، حداکثر افت، بازده کل، win rate
  * `plot_equity_curve(metrics)` — ذخیره تصویر منحنی سرمایه
  * استراتژی‌های آماده: ma_cross, rsi_reversion

Usage:
    engine = VectorizedBacktestEngine(data)
    metrics = engine.run_strategy(ma_cross_strategy)
    engine.plot_equity_curve(metrics)
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Callable

logger = logging.getLogger(__name__)

try:
    import pandas as pd
    import numpy as np
except ImportError:  # pragma: no cover
    logger.warning("pandas/numpy not installed — vectorized engine unavailable")
    pd = None  # type: ignore
    np = None  # type: ignore

# ── Required OHLCV columns ─────────────────────────────────────────────────
REQUIRED_COLUMNS = ("price_close", "price_open", "price_high", "price_low", "trade_volume")

ANNUAL_TRADING_DAYS = 250
RISK_FREE_RATE = 0.0


def _require_pandas() -> None:
    if pd is None or np is None:
        raise RuntimeError("pandas/numpy are required for the vectorized engine")


# ═══════════════════════════════════════════════════════════════════════════
#  ENGINE
# ═══════════════════════════════════════════════════════════════════════════

class VectorizedBacktestEngine:
    """Runs signal functions on a DataFrame and computes key metrics."""

    def __init__(self, data: "pd.DataFrame") -> None:
        _require_pandas()
        missing = [c for c in REQUIRED_COLUMNS if c not in data.columns]
        if missing:
            raise ValueError(f"Missing columns: {missing}. Required: {REQUIRED_COLUMNS}")
        self.data = data.copy()
        self.data["returns"] = self.data["price_close"].pct_change().fillna(0.0)
        self._strategy_returns: "pd.Series | None" = None
        self._equity_curve: "pd.Series | None" = None

    # ── Run ──────────────────────────────────────────────────────────────

    def run_strategy(
        self,
        strategy_func: Callable[["pd.DataFrame"], "pd.Series | np.ndarray"],
    ) -> dict[str, Any]:
        """
        Run a strategy and compute metrics.

        strategy_func receives the full DataFrame (with OHLCV + returns) and
        must return a signal series: 1 = long, -1 = short, 0 = flat.
        Positions are applied with a one-day lag to avoid look-ahead bias.
        """
        signals = strategy_func(self.data)
        if isinstance(signals, np.ndarray):
            signals = pd.Series(signals, index=self.data.index)
        signals = signals.fillna(0.0).clip(-1, 1)

        # Position shifted by one day → signal on day T trades from day T+1
        position = signals.shift(1).fillna(0.0)
        self._strategy_returns = position * self.data["returns"]
        self._equity_curve = (1.0 + self._strategy_returns).cumprod()

        metrics = self.calculate_metrics(self._strategy_returns)
        metrics["signal_count"] = int((signals != 0).sum())
        metrics["equity_curve"] = self._equity_curve
        return metrics

    # ── Metrics ──────────────────────────────────────────────────────────

    def calculate_metrics(
        self,
        returns: "pd.Series",
    ) -> dict[str, Any]:
        """Sharpe, Sortino, max drawdown, total return, win rate, ..."""
        _require_pandas()
        returns = returns.dropna()
        n = len(returns)
        if n == 0:
            return {"total_return": 0.0, "annual_return": 0.0,
                    "sharpe_ratio": 0.0, "sortino_ratio": 0.0,
                    "max_drawdown": 0.0, "win_rate": 0.0, "volatility": 0.0}

        total_return = float((1.0 + returns).prod() - 1.0)
        annual_return = float((1.0 + total_return) ** (ANNUAL_TRADING_DAYS / max(n, 1)) - 1.0)
        volatility = float(returns.std(ddof=0) * (ANNUAL_TRADING_DAYS ** 0.5))

        excess = returns - RISK_FREE_RATE / ANNUAL_TRADING_DAYS
        sharpe = float(excess.mean() / returns.std(ddof=0) * (ANNUAL_TRADING_DAYS ** 0.5)) \
            if returns.std(ddof=0) > 0 else 0.0

        downside = returns[returns < 0]
        downside_std = float(downside.std(ddof=0)) if len(downside) > 1 else 0.0
        sortino = float(returns.mean() / downside_std * (ANNUAL_TRADING_DAYS ** 0.5)) \
            if downside_std > 0 else 0.0

        equity = (1.0 + returns).cumprod()
        peak = equity.cummax()
        drawdown = (equity - peak) / peak
        max_drawdown = float(drawdown.min())

        wins = returns[returns > 0]
        win_rate = float(len(wins) / n) * 100.0

        return {
            "total_return": round(total_return * 100, 2),
            "annual_return": round(annual_return * 100, 2),
            "sharpe_ratio": round(sharpe, 3),
            "sortino_ratio": round(sortino, 3),
            "max_drawdown": round(max_drawdown * 100, 2),
            "win_rate": round(win_rate, 1),
            "volatility": round(volatility * 100, 2),
            "n_periods": n,
        }

    # ── Plot ─────────────────────────────────────────────────────────────

    def plot_equity_curve(self, metrics: dict[str, Any], output: str = "equity_curve.png") -> str:
        """
        Save an equity-curve PNG. Returns the output path.

        Uses matplotlib (optional dependency) — if unavailable, writes a
        minimal HTML/SVG fallback so callers still get a visual.
        """
        curve = metrics.get("equity_curve")
        if curve is None:
            curve = self._equity_curve
        if curve is None:
            raise ValueError("No equity curve available — run a strategy first")

        out_path = Path(output)
        try:
            import matplotlib
            matplotlib.use("Agg")
            import matplotlib.pyplot as plt

            fig, ax = plt.subplots(figsize=(10, 5))
            ax.plot(curve.index, curve.values, lw=1.5, label="Equity")
            ax.set_title(f"Equity Curve — Sharpe {metrics.get('sharpe_ratio', 0)}")
            ax.set_xlabel("Period")
            ax.set_ylabel("Growth (×)")
            ax.grid(alpha=0.3)
            ax.legend()
            fig.tight_layout()
            fig.savefig(out_path, dpi=120)
            plt.close(fig)
            logger.info("Saved equity curve to %s", out_path)
            return str(out_path)
        except ImportError:  # pragma: no cover — matplotlib optional
            logger.warning("matplotlib not installed — writing SVG fallback")
            svg_path = out_path.with_suffix(".svg")
            points = "\n".join(
                f'<polyline points="0,0" style="display:none"/>'  # noqa: E501
            )
            path_d = " ".join(
                f"L{x},{100 - float(v) * 100}"
                for x, v in enumerate(curve.values)
            )
            svg = (
                '<svg xmlns="http://www.w3.org/2000/svg" width="800" height="400" '
                'viewBox="0 0 800 400"><polyline points="0,200 '
                f'{path_d}" fill="none" stroke="#0ea5e9" stroke-width="2"/></svg>'
            )
            svg_path.write_text(svg, encoding="utf-8")
            return str(svg_path)


# ═══════════════════════════════════════════════════════════════════════════
#  READY-MADE STRATEGIES
# ═══════════════════════════════════════════════════════════════════════════

def ma_cross_strategy(
    data: "pd.DataFrame",
    fast: int = 20,
    slow: int = 50,
) -> "pd.Series":
    """MA cross: +1 when fast > slow, -1 when fast < slow."""
    _require_pandas()
    fast_ma = data["price_close"].rolling(fast).mean()
    slow_ma = data["price_close"].rolling(slow).mean()
    return (fast_ma > slow_ma).astype(float) - (fast_ma < slow_ma).astype(float)


def rsi_reversion_strategy(
    data: "pd.DataFrame",
    period: int = 14,
    buy_below: float = 30.0,
    sell_above: float = 70.0,
) -> "pd.Series":
    """RSI mean-reversion: +1 when oversold, -1 when overbought."""
    _require_pandas()
    rsi = _rsi_series(data["price_close"], period)
    signals = pd.Series(0.0, index=data.index)
    signals[rsi < buy_below] = 1.0
    signals[rsi > sell_above] = -1.0
    return signals


def _rsi_series(closes: "pd.Series", period: int = 14) -> "pd.Series":
    delta = closes.diff()
    gain = delta.clip(lower=0.0)
    loss = -delta.clip(upper=0.0)
    avg_gain = gain.ewm(alpha=1 / period, min_periods=period).mean()
    avg_loss = loss.ewm(alpha=1 / period, min_periods=period).mean()
    rs = avg_gain / avg_loss.replace(0.0, np.nan)
    rsi = 100.0 - (100.0 / (1.0 + rs))
    return rsi.fillna(50.0)


# ═══════════════════════════════════════════════════════════════════════════
#  CONVENIENCE WRAPPER
# ═══════════════════════════════════════════════════════════════════════════

def run_vectorized_backtest(
    data: "pd.DataFrame",
    strategy: str = "ma_cross",
    **strategy_kwargs: Any,
) -> dict[str, Any]:
    """One-call wrapper: pick a built-in strategy and run it."""
    engine = VectorizedBacktestEngine(data)
    if strategy == "ma_cross":
        fn: Callable = ma_cross_strategy
    elif strategy == "rsi_reversion":
        fn = rsi_reversion_strategy
    else:
        raise ValueError(f"Unknown strategy: {strategy}. Use ma_cross or rsi_reversion")
    return engine.run_strategy(lambda df: fn(df, **strategy_kwargs))
