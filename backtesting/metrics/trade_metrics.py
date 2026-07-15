from __future__ import annotations

import numpy as np

from backtesting.types import BacktestResult


class TradeMetrics:
    @staticmethod
    def compute(result: BacktestResult) -> dict[str, float]:
        metrics: dict[str, float] = {}
        trades = result.trades
        if not trades:
            return {"total_trades": 0, "win_rate": 0.0, "avg_profit": 0.0}
        metrics["total_trades"] = float(len(trades))
        buy_trades = [t for t in trades if t.side == "buy"]
        sell_trades = [t for t in trades if t.side == "sell"]
        metrics["buy_trades"] = float(len(buy_trades))
        metrics["sell_trades"] = float(len(sell_trades))

        # BUG FIX #7: Compute PnL by pairing buys with sells per instrument
        # Each buy-sell pair forms one round-trip trade
        round_trips: list[float] = []
        open_buys: dict[str, list[tuple[float, int]]] = {}  # inst_id -> [(price, qty)]
        for t in trades:
            key = t.instrument_id or "default"
            if t.side == "buy":
                open_buys.setdefault(key, []).append((t.price, t.quantity))
            elif t.side == "sell":
                buys = open_buys.get(key, [])
                if buys:
                    buy_price, buy_qty = buys.pop(0)
                    matched_qty = min(buy_qty, t.quantity)
                    pnl = (t.price - buy_price) * matched_qty - t.commission
                    round_trips.append(pnl)
                    if buy_qty > matched_qty:
                        buys.insert(0, (buy_price, buy_qty - matched_qty))

        # Fallback: if no round trips (e.g., only buys or only sells), use raw values
        if not round_trips:
            round_trips = [t.price * t.quantity * (1 if t.side == "sell" else -1) for t in trades]

        winning = [p for p in round_trips if p > 0]
        losing = [p for p in round_trips if p < 0]
        metrics["win_rate"] = (len(winning) / len(round_trips)) * 100 if round_trips else 0.0
        metrics["avg_profit"] = float(np.mean(round_trips)) if round_trips else 0.0
        metrics["avg_win"] = float(np.mean(winning)) if winning else 0.0
        metrics["avg_loss"] = float(np.mean(losing)) if losing else 0.0
        metrics["profit_factor"] = abs(sum(winning) / sum(losing)) if losing and sum(losing) != 0 else 0.0
        metrics["largest_win"] = float(max(round_trips)) if round_trips else 0.0
        metrics["largest_loss"] = float(min(round_trips)) if round_trips else 0.0
        metrics["total_pnl"] = float(sum(round_trips))

        # Compute avg trade duration from buy/sell pairs
        durations: list[float] = []
        open_positions: dict[str, float] = {}
        for t in trades:
            key = t.instrument_id or "default"
            ts = t.timestamp.timestamp() if hasattr(t.timestamp, "timestamp") else 0
            if t.side == "buy":
                open_positions[key] = ts
            elif t.side == "sell" and key in open_positions:
                duration_days = (ts - open_positions[key]) / 86400
                if duration_days >= 0:
                    durations.append(duration_days)
                del open_positions[key]
        metrics["avg_trade_duration"] = float(np.mean(durations)) if durations else 0.0
        metrics["max_trade_duration"] = float(max(durations)) if durations else 0.0
        metrics["min_trade_duration"] = float(min(durations)) if durations else 0.0

        # Consecutive wins/losses
        max_consec_wins = 0
        max_consec_losses = 0
        cur_wins = 0
        cur_losses = 0
        for p in round_trips:
            if p > 0:
                cur_wins += 1
                cur_losses = 0
            else:
                cur_losses += 1
                cur_wins = 0
            max_consec_wins = max(max_consec_wins, cur_wins)
            max_consec_losses = max(max_consec_losses, cur_losses)
        metrics["max_consecutive_wins"] = float(max_consec_wins)
        metrics["max_consecutive_losses"] = float(max_consec_losses)

        return metrics
