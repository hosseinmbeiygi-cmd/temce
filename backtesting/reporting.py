from __future__ import annotations

from typing import Any

from core.logging import get_logger

logger = get_logger(__name__)


class BacktestReporting:
    def build_report(self, result: Any) -> dict[str, Any]:
        return {
            "summary": {},
            "metrics": {},
            "trades": [],
            "equity_curve": [],
            "attribution": {},
        }

    def to_html(self, report: dict[str, Any]) -> str:
        return "<html><body><h1>Backtest Report</h1></body></html>"

    def to_json(self, report: dict[str, Any]) -> dict[str, Any]:
        return report
