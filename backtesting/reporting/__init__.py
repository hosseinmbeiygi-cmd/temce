from __future__ import annotations

from typing import Any

from backtesting.reporting.equity_curve import EquityCurveReport
from backtesting.reporting.html_report import HTMLReport
from backtesting.reporting.json_report import JSONReport
from backtesting.reporting.pdf_report import PDFReport
from backtesting.reporting.report_builder import ReportBuilder
from backtesting.reporting.summary_report import SummaryReport
from backtesting.reporting.trade_log_report import TradeLogReport


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


__all__ = [
    "ReportBuilder",
    "SummaryReport",
    "EquityCurveReport",
    "TradeLogReport",
    "HTMLReport",
    "JSONReport",
    "PDFReport",
    "BacktestReporting",
]
