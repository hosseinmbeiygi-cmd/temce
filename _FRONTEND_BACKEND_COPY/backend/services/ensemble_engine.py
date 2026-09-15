"""Strategy Ensemble Engine for Tehran Stock Exchange.

Combines signals from multiple strategies using regime-based weighting.
In bullish regimes, trend-following strategies get higher weight.
In range regimes, mean-reversion strategies get higher weight.
"""

from __future__ import annotations

import math
from typing import Any

from core.logging import get_logger

logger = get_logger(__name__)


class StrategyEnsemble:
    """Combine multiple strategy signals with regime-based weighting."""

    STRATEGY_TYPES = {
        "trend": ["moving_average_cross", "half_trend", "squeeze_momentum"],
        "momentum": ["momentum", "breakout", "volatility_breakout"],
        "reversion": ["mean_reversion", "rsi_reversion"],
        "technical": ["support_resistance"],
    }

    REGIME_WEIGHTS = {
        0: {  # Bearish
            "trend": 0.1,
            "momentum": 0.1,
            "reversion": 0.6,
            "technical": 0.2,
        },
        1: {  # Neutral/Range
            "trend": 0.2,
            "momentum": 0.2,
            "reversion": 0.4,
            "technical": 0.2,
        },
        2: {  # Bullish
            "trend": 0.4,
            "momentum": 0.3,
            "reversion": 0.15,
            "technical": 0.15,
        },
    }

    def __init__(self):
        self.strategy_scores: dict[str, float] = {}
        self.regime_history: list[int] = []

    def get_strategy_type(self, strategy_name: str) -> str:
        for stype, names in self.STRATEGY_TYPES.items():
            if strategy_name in names:
                return stype

        return "other"

    def combine_signals(
        self, signals: list[dict[str, Any]], regime: int = 1, confidence_threshold: float = 0.3
    ) -> dict[str, Any]:
        """Combine multiple strategy signals into a final decision.

        Args:
            signals: List of {strategy, symbol, signal, score, params}
            regime: Current market regime (0=bearish, 1=neutral, 2=bullish)
            confidence_threshold: Minimum combined confidence to act

        Returns:
            {action, confidence, breakdown, regime_label}
        """
        if not signals:
            return {"action": "HOLD", "confidence": 0, "breakdown": {}, "regime_label": self._regime_label(regime)}

        regime_weights = self.REGIME_WEIGHTS.get(regime, self.REGIME_WEIGHTS[1])

        # Group signals by symbol
        symbol_signals: dict[str, list[dict[str, Any]]] = {}
        for sig in signals:
            sym = sig.get("symbol", "")
            if sym not in symbol_signals:
                symbol_signals[sym] = []

            symbol_signals[sym].append(sig)

        results = {}
        for sym, sym_sigs in symbol_signals.items():
            weighted_score = 0.0
            total_weight = 0.0
            breakdown = {}

            for sig in sym_sigs:
                stype = self.get_strategy_type(sig.get("strategy", ""))
                weight = regime_weights.get(stype, 0.25)
                raw_score = sig.get("score", 0)  # -1 to +1
                weighted_score += weight * raw_score
                total_weight += weight
                breakdown[sig.get("strategy", "?")] = {
                    "type": stype,
                    "raw_score": round(raw_score, 3),
                    "weight": round(weight, 3),
                    "weighted": round(weight * raw_score, 3),
                }

            final_score = weighted_score / max(total_weight, 0.001)
            confidence = abs(final_score)

            if final_score > confidence_threshold:
                action = "BUY"

            elif final_score < -confidence_threshold:
                action = "SELL"
            else:
                action = "HOLD"

            results[sym] = {
                "action": action,
                "confidence": round(confidence, 3),
                "final_score": round(final_score, 3),
                "breakdown": breakdown,
                "regime_label": self._regime_label(regime),
                "regime_weights": {k: round(v, 2) for k, v in regime_weights.items()},
            }

        return results

    def _regime_label(self, regime: int) -> str:
        return {0: "نزولی", 1: "نوسانی", 2: "صعودی"}.get(regime, "نامشخص")

    def update_strategy_performance(self, strategy_name: str, return_pct: float, sharpe: float):
        """Update strategy performance for adaptive weighting."""
        score = sharpe * 0.6 + (return_pct / 100) * 0.4
        self.strategy_scores[strategy_name] = score


class RiskGate:
    """CVaR-based risk gate that adjusts position weights."""

    def __init__(self, alpha: float = 0.95, max_cvar: float = 0.03, max_position_pct: float = 0.20):
        self.alpha = alpha
        self.max_cvar = max_cvar
        self.max_position_pct = max_position_pct

    def compute_var(self, returns: list[float]) -> float:
        if not returns:
            return 0.0

        sorted_r = sorted(returns)
        idx = int((1 - self.alpha) * len(sorted_r))
        return -sorted_r[min(idx, len(sorted_r) - 1)]

    def compute_cvar(self, returns: list[float]) -> float:
        if not returns:
            return 0.0

        sorted_r = sorted(returns)
        cutoff = int((1 - self.alpha) * len(sorted_r))
        if cutoff <= 0:
            return -sorted_r[0] if sorted_r else 0.0

        return -sum(sorted_r[:cutoff]) / cutoff

    def adjust_weights(self, weights: dict[str, float], returns_history: dict[str, list[float]]) -> dict[str, float]:
        """Adjust portfolio weights based on CVaR limits."""
        adjusted = {}
        for symbol, weight in weights.items():
            hist = returns_history.get(symbol, [])
            if hist:
                cvar = self.compute_cvar(hist)

                if cvar > self.max_cvar:
                    reduction = min(1.0, cvar / self.max_cvar)

                    weight *= max(0.1, 1.0 - reduction * 0.8)
                    logger.info("RiskGate: %s CVaR=%.3f > limit, reducing weight to %.2f", symbol, cvar, weight)
            adjusted[symbol] = min(weight, self.max_position_pct)

        # Normalize
        total = sum(adjusted.values())
        if total > 0:
            adjusted = {k: v / total for k, v in adjusted.items()}

        return adjusted


class TSESimulator:
    """High-fidelity TSE simulator with queue dynamics, price limits, and commission structures.

    Models:
    - Daily price limits (دامنه نوسان ±5%)
    - Buy/sell queue lockups with probabilistic fill
    - Commission: buy ~0.37%, sell ~0.88% (includes tax)
    - Slippage based on market depth
    - Base volume effect (حجم مبنا)
    """

    def __init__(
        self,
        commission_buy: float = 0.003712,
        commission_sell: float = 0.0088,
        slippage: float = 0.001,
        queue_fill_rate: float = 0.7,
        cancellation_rate: float = 0.05,
    ):
        self.comm_buy = commission_buy
        self.comm_sell = commission_sell
        self.slippage = slippage
        self.queue_fill_rate = queue_fill_rate
        self.cancellation_rate = cancellation_rate

    def calculate_price_limits(self, yesterday_close: float, limit_pct: float = 0.05) -> tuple[float, float]:
        high_limit = yesterday_close * (1 + limit_pct)
        low_limit = yesterday_close * (1 - limit_pct)
        return low_limit, high_limit

    def apply_base_volume(self, raw_return: float, traded_volume: float, base_volume: float) -> float:
        if base_volume <= 0:
            return raw_return

        ratio = min(1.0, traded_volume / base_volume)
        return raw_return * ratio

    def simulate_order(
        self, bar: dict, order_side: str, order_size: float, limit_price: float, queue_position: float | None = None
    ) -> dict:
        yesterday_close = bar.get("yesterday_close", bar.get("close", 0))
        low_limit, high_limit = self.calculate_price_limits(yesterday_close)
        close = bar.get("close", 0)
        volume = bar.get("volume", 0)
        bid_queue = bar.get("bid_queue_size", bar.get("queue_buy", 0))
        ask_queue = bar.get("ask_queue_size", bar.get("queue_sell", 0))

        if limit_price > high_limit or limit_price < low_limit:
            return {"status": "REJECTED", "reason": "Price exceeds daily limits", "filled_qty": 0}

        is_buy_lock = (close >= high_limit) and (bid_queue > 0)
        is_sell_lock = (close <= low_limit) and (ask_queue > 0)

        if (order_side == "BUY" and not is_buy_lock) or (order_side == "SELL" and not is_sell_lock):
            price = limit_price * (1 + self.slippage if order_side == "BUY" else 1 - self.slippage)

            commission = order_size * price * (self.comm_buy if order_side == "BUY" else self.comm_sell)
            return {"status": "FILLED", "filled_qty": order_size, "price": price, "commission": commission}

        queue_size = bid_queue if order_side == "BUY" else ask_queue
        pos = queue_position if queue_position is not None else queue_size
        market_exec = volume * self.queue_fill_rate
        cancellations = pos * self.cancellation_rate
        remaining = max(0.0, pos - market_exec - cancellations)

        if remaining == 0:
            price = limit_price

            commission = order_size * price * (self.comm_buy if order_side == "BUY" else self.comm_sell)
            return {
                "status": "FILLED",
                "filled_qty": order_size,
                "price": price,
                "commission": commission,
                "reason": "Queue cleared",
            }

        return {"status": "QUEUED", "filled_qty": 0, "price": 0, "commission": 0, "remaining_pos": remaining}

    def simulate(self, data: list[dict], signals: list[int], capital: float = 1_000_000_000) -> dict[str, Any]:
        cash = capital
        position = 0
        entry_price = 0
        equity_curve = []
        trades = []
        pending_queue: dict[str, float] = {}

        for i, bar in enumerate(data):
            if i >= len(signals):
                break

            close = bar.get("close", 0)
            signal = signals[i]
            bar.get("yesterday_close", close)

            if signal == 1 and position == 0 and cash > 1000:
                invest = cash * 0.95

                order_size = invest / close
                result = self.simulate_order(bar, "BUY", order_size, close)
                if result["status"] == "FILLED":
                    position = result["filled_qty"]

                    entry_price = result["price"]
                    cash -= result["filled_qty"] * result["price"] + result["commission"]
                    trades.append(
                        {
                            "type": "BUY",
                            "price": result["price"],
                            "shares": result["filled_qty"],
                            "fee": result["commission"],
                        }
                    )
                elif result["status"] == "QUEUED":
                    pending_queue["buy"] = result.get("remaining_pos", 0)

            elif signal == -1 and position > 0:
                result = self.simulate_order(bar, "SELL", position, close)
                if result["status"] == "FILLED":
                    pnl = (result["price"] - entry_price) * position - result["commission"]

                    cash += result["filled_qty"] * result["price"] - result["commission"]
                    trades.append(
                        {
                            "type": "SELL",
                            "price": result["price"],
                            "shares": position,
                            "fee": result["commission"],
                            "pnl": pnl,
                        }
                    )
                    position = 0

            equity = cash + position * close
            equity_curve.append(equity)

        if len(equity_curve) < 2:
            return {"equity_curve": equity_curve, "trades": trades, "metrics": {}}

        total_return = (equity_curve[-1] / capital - 1) * 100
        returns = [
            (equity_curve[j] / equity_curve[j - 1]) - 1 for j in range(1, len(equity_curve)) if equity_curve[j - 1] > 0
        ]
        avg_r = sum(returns) / len(returns) if returns else 0
        std_r = math.sqrt(sum((r - avg_r) ** 2 for r in returns) / len(returns)) if returns else 1
        sharpe = (avg_r / std_r) * math.sqrt(252) if std_r > 0 else 0

        peak = equity_curve[0]
        max_dd = 0.0
        for v in equity_curve:
            if v > peak:
                peak = v

            dd = (peak - v) / peak if peak > 0 else 0
            max_dd = max(max_dd, dd)

        wins = [t for t in trades if t.get("pnl", 0) > 0]
        losses = [t for t in trades if t.get("pnl", 0) < 0]
        total_trades = len([t for t in trades if t["type"] == "SELL"])
        win_rate = len(wins) / max(total_trades, 1) * 100

        return {
            "equity_curve": equity_curve,
            "trades": trades,
            "metrics": {
                "total_return_pct": round(total_return, 2),
                "sharpe_ratio": round(sharpe, 2),
                "max_drawdown_pct": round(max_dd * 100, 2),
                "total_trades": total_trades,
                "winning_trades": len(wins),
                "losing_trades": len(losses),
                "win_rate": round(win_rate, 1),
                "final_capital": round(equity_curve[-1], 0),
            },
        }


# ── Database Schema (TimescaleDB) ─────────────────────────────────────────────────────────────────────────────────────────────────────

TIMESCALE_SCHEMA = """
-- Enable TimescaleDB extension
CREATE EXTENSION IF NOT EXISTS timescaledb CASCADE;

-- Bar data (OHLCV with queue info)
CREATE TABLE IF NOT EXISTS bar_data (
    time TIMESTAMPTZ NOT NULL,
    symbol VARCHAR(20) NOT NULL,
    open DOUBLE PRECISION NOT NULL,
    high DOUBLE PRECISION NOT NULL,
    low DOUBLE PRECISION NOT NULL,
    close DOUBLE PRECISION NOT NULL,
    volume DOUBLE PRECISION NOT NULL,
    value DOUBLE PRECISION NOT NULL,
    trades_count INT,
    queue_buy_volume DOUBLE PRECISION,
    queue_sell_volume DOUBLE PRECISION,
    limit_up DOUBLE PRECISION,
    limit_down DOUBLE PRECISION
);

SELECT create_hypertable('bar_data', 'time', chunk_time_interval => INTERVAL '7 days', if_not_exists => TRUE);
CREATE INDEX IF NOT EXISTS idx_bar_symbol_time ON bar_data (symbol, time DESC);

-- Market regimes
CREATE TABLE IF NOT EXISTS market_regimes (
    time TIMESTAMPTZ NOT NULL,
    regime INT NOT NULL,
    confidence DOUBLE PRECISION,
    features JSONB
);

SELECT create_hypertable('market_regimes', 'time', chunk_time_interval => INTERVAL '30 days', if_not_exists => TRUE);

-- Trading signals
CREATE TABLE IF NOT EXISTS trading_signals (
    time TIMESTAMPTZ NOT NULL,
    symbol VARCHAR(20) NOT NULL,
    strategy VARCHAR(50) NOT NULL,
    signal INT NOT NULL,
    score DOUBLE PRECISION,
    regime INT,
    risk_adjusted BOOLEAN DEFAULT FALSE,
    cvar_value DOUBLE PRECISION,
    executed BOOLEAN DEFAULT FALSE
);

SELECT create_hypertable('trading_signals', 'time', chunk_time_interval => INTERVAL '7 days', if_not_exists => TRUE);
CREATE INDEX IF NOT EXISTS idx_sig_symbol ON trading_signals (symbol, time DESC);

-- Strategy performance
CREATE TABLE IF NOT EXISTS strategy_performance (
    time TIMESTAMPTZ NOT NULL,
    strategy VARCHAR(50) NOT NULL,
    symbol VARCHAR(20),
    return_pct DOUBLE PRECISION,
    sharpe DOUBLE PRECISION,
    max_drawdown DOUBLE PRECISION,
    total_trades INT,
    win_rate DOUBLE PRECISION
);

SELECT create_hypertable('strategy_performance', 'time', chunk_time_interval => INTERVAL '30 days', if_not_exists => TRUE);

-- Portfolio positions
CREATE TABLE IF NOT EXISTS portfolio_positions (
    time TIMESTAMPTZ NOT NULL,
    symbol VARCHAR(20) NOT NULL,
    qty DOUBLE PRECISION,
    avg_price DOUBLE PRECISION,
    market_value DOUBLE PRECISION,
    unrealized_pnl DOUBLE PRECISION,
    weight DOUBLE PRECISION
);

SELECT create_hypertable('portfolio_positions', 'time', chunk_time_interval => INTERVAL '1 day', if_not_exists => TRUE);
"""
