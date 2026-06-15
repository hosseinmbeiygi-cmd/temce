from __future__ import annotations

from typing import Any

from backtesting.types import BacktestResult


class SummaryReport:
    @staticmethod
    def generate(result: BacktestResult) -> dict[str, Any]:
        return {
            "strategy_name": result.strategy_name,
            "initial_capital": result.initial_capital,
            "final_capital": result.final_capital,
            "total_return": result.total_return,
            "total_return_pct": result.total_return_pct,
            "total_trades": result.total_trades,
            "win_rate": result.win_rate,
            "sharpe_ratio": result.sharpe_ratio,
            "max_drawdown": result.max_drawdown,
            "metrics": result.metrics,
            "metadata": result.metadata,
        }

    @staticmethod
    def to_text(result: BacktestResult) -> str:
        lines = [
            "=" * 50,
            f"Strategy: {result.strategy_name}",
            "=" * 50,
            f"Initial Capital: {result.initial_capital:,.0f}",
            f"Final Capital:   {result.final_capital:,.0f}",
            f"Total Return:    {result.total_return:,.0f} ({result.total_return_pct:.2f}%)",
            f"Total Trades:    {result.total_trades}",
            f"Win Rate:        {result.win_rate:.2f}%",
            f"Sharpe Ratio:    {result.sharpe_ratio:.4f}",
            f"Max Drawdown:    {result.max_drawdown:.2f}%",
            "-" * 50,
        ]
        return "\n".join(lines)
