from __future__ import annotations

from typing import Any

from backtesting.types import BacktestResult


class EquityCurveReport:
    @staticmethod
    def generate(result: BacktestResult) -> list[dict[str, Any]]:
        return [
            {
                "timestamp": p.timestamp.isoformat() if hasattr(p.timestamp, "isoformat") else str(p.timestamp),
                "nav": p.nav,
                "cash": p.cash,
                "positions_value": p.positions_value,
                "return_pct": ((p.nav / result.initial_capital) - 1) * 100 if result.initial_capital > 0 else 0.0,
            }
            for p in result.equity_curve
        ]

    @staticmethod
    def to_csv_lines(result: BacktestResult) -> list[str]:
        lines = ["timestamp,nav,cash,positions_value,return_pct"]
        for p in result.equity_curve:
            ts = p.timestamp.isoformat() if hasattr(p.timestamp, "isoformat") else str(p.timestamp)
            ret = ((p.nav / result.initial_capital) - 1) * 100 if result.initial_capital > 0 else 0.0
            lines.append(f"{ts},{p.nav},{p.cash},{p.positions_value},{ret:.4f}")
        return lines
