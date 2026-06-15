from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from backtesting.types import BacktestResult


class BacktestReportBuilder:
    def build(self, result: BacktestResult) -> dict[str, Any]:
        return {
            "strategy": result.strategy_name,
            "initial_capital": result.initial_capital,
            "final_capital": result.final_capital,
            "total_return": result.total_return,
            "total_return_pct": result.total_return_pct,
            "sharpe_ratio": result.sharpe_ratio,
            "max_drawdown": result.max_drawdown,
            "total_trades": result.total_trades,
            "win_rate": result.win_rate,
            "timestamp": datetime.now(UTC).isoformat(),
            "metrics": result.metrics,
        }

    def build_html(self, result: BacktestResult) -> str:
        data = self.build(result)
        lines = ["<html><body><h1>Backtest Report</h1><table>"]
        for key, value in data.items():
            if key != "metrics":
                lines.append(f"<tr><td>{key}</td><td>{value}</td></tr>")
        lines.append("</table></body></html>")
        return "\n".join(lines)
