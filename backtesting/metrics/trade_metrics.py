from __future__ import annotations

from collections import deque

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
        # Each buy-sell pair forms one round-trip trade.
        # FIFO cost-basis PnL (audit F4): the buy-side commission is spread over
        # the matched share and included in the PnL (not only the sell side).
        #   cost_basis = buy_price + buy_commission_used / matched_qty
        #   pnl = (sell_price - cost_basis) * matched_qty - sell_commission_used
        # A deque keeps FIFO opening O(1) instead of O(n) with pop(0).
        round_trips: list[float] = []
        open_buys: dict[str, deque] = {}  # inst_id -> deque[(price, qty_remaining, commission_remaining)]
        for t in trades:
            key = t.instrument_id or "default"
            if t.side == "buy":
                open_buys.setdefault(key, deque()).append((t.price, t.quantity, t.commission))
            elif t.side == "sell":
                buys = open_buys.get(key)
                remaining_sell = max(t.quantity, 0)
                sell_comm_per_unit = t.commission / max(t.quantity, 1)
                while buys and remaining_sell > 0:
                    buy_price, buy_qty, buy_commission = buys.popleft()
                    matched_qty = min(buy_qty, remaining_sell)
                    buy_comm_used = buy_commission * (matched_qty / max(buy_qty, 1))
                    cost_basis = buy_price + buy_comm_used / max(matched_qty, 1)
                    sell_comm_used = sell_comm_per_unit * matched_qty
                    pnl = (t.price - cost_basis) * matched_qty - sell_comm_used
                    round_trips.append(pnl)
                    remaining_sell -= matched_qty
                    if buy_qty > matched_qty:
                        buys.appendleft((
                            buy_price,
                            buy_qty - matched_qty,
                            buy_commission - buy_comm_used,
                        ))

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
        open_positions: dict[str, deque[tuple[float, int]]] = {}
        for t in trades:
            key = t.instrument_id or "default"
            ts = t.timestamp.timestamp() if hasattr(t.timestamp, "timestamp") else 0
            if t.side == "buy":
                open_positions.setdefault(key, deque()).append((ts, t.quantity))
            elif t.side == "sell":
                remaining_sell = max(t.quantity, 0)
                positions = open_positions.get(key)
                while positions and remaining_sell > 0:
                    opened_at, opened_qty = positions.popleft()
                    matched_qty = min(opened_qty, remaining_sell)
                    duration_days = (ts - opened_at) / 86400
                    if duration_days >= 0:
                        durations.append(duration_days)
                    remaining_sell -= matched_qty
                    if opened_qty > matched_qty:
                        positions.appendleft((opened_at, opened_qty - matched_qty))
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
            elif p < 0:
                cur_losses += 1
                cur_wins = 0
            else:
                # A flat trade is neither a win nor a loss and must break
                # both streaks instead of being counted as a loss.
                cur_wins = 0
                cur_losses = 0
            max_consec_wins = max(max_consec_wins, cur_wins)
            max_consec_losses = max(max_consec_losses, cur_losses)
        metrics["max_consecutive_wins"] = float(max_consec_wins)
        metrics["max_consecutive_losses"] = float(max_consec_losses)

        return metrics
