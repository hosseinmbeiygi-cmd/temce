from __future__ import annotations

from typing import Any

from backtesting.types import BacktestResult


class ReportBuilder:
    def __init__(self) -> None:
        self._sections: dict[str, Any] = {}

    def add_section(self, name: str, data: Any) -> None:
        self._sections[name] = data

    def build(self, result: BacktestResult) -> dict[str, Any]:
        report: dict[str, Any] = {
            "strategy": result.strategy_name,
            "initial_capital": result.initial_capital,
            "final_capital": result.final_capital,
            "total_return": result.total_return,
            "total_return_pct": result.total_return_pct,
            "total_trades": result.total_trades,
            "metrics": result.metrics,
            "metadata": result.metadata,
        }
        report.update(self._sections)
        return report

    def clear(self) -> None:
        self._sections.clear()
