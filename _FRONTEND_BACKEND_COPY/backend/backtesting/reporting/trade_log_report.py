from __future__ import annotations

from typing import Any

from backtesting.types import BacktestResult


class TradeLogReport:
    @staticmethod
    def generate(result: BacktestResult) -> list[dict[str, Any]]:
        return [
            {
                "order_id": t.order_id,
                "instrument_id": t.instrument_id,
                "side": t.side,
                "quantity": t.quantity,
                "price": t.price,
                "commission": t.commission,
                "timestamp": t.timestamp.isoformat() if hasattr(t.timestamp, "isoformat") else str(t.timestamp),
                "total_value": t.price * t.quantity,
            }
            for t in result.trades
        ]

    @staticmethod
    def to_csv_lines(result: BacktestResult) -> list[str]:
        lines = ["order_id,instrument_id,side,quantity,price,commission,timestamp,total_value"]
        for t in result.trades:
            ts = t.timestamp.isoformat() if hasattr(t.timestamp, "isoformat") else str(t.timestamp)
            lines.append(
                f"{t.order_id},{t.instrument_id},{t.side},{t.quantity},{t.price},{t.commission},{ts},{t.price * t.quantity}"
            )
        return lines
