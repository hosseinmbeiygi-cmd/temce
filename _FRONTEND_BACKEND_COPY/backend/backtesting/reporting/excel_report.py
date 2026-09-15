from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass
class ExcelSheet:
    name: str
    headers: list[str]
    rows: list[list[Any]]


@dataclass
class ExcelReportConfig:
    title: str = "Backtest Report"
    author: str = "Backtesting Engine"
    include_charts: bool = True
    include_metrics: bool = True
    include_trades: bool = True
    include_equity_curve: bool = True
    include_drawdown: bool = True
    include_monthly_returns: bool = True
    include_attribution: bool = False
    include_sensitivity: bool = False
    persian_format: bool = True


class ExcelReport:
    def __init__(self, config: ExcelReportConfig | None = None) -> None:
        self._config = config or ExcelReportConfig()

    @property
    def config(self) -> ExcelReportConfig:
        return self._config

    def generate(
        self,
        metrics: dict[str, Any],
        equity_curve: list[dict[str, Any]] | None = None,
        trades: list[dict[str, Any]] | None = None,
        monthly_returns: list[dict[str, Any]] | None = None,
        drawdown: list[dict[str, Any]] | None = None,
        attribution: dict[str, Any] | None = None,
        sensitivity: dict[str, Any] | None = None,
    ) -> list[ExcelSheet]:
        sheets: list[ExcelSheet] = []

        if self._config.include_metrics:
            sheets.append(self._build_metrics_sheet(metrics))

        if self._config.include_equity_curve and equity_curve:
            sheets.append(self._build_equity_curve_sheet(equity_curve))

        if self._config.include_drawdown and drawdown:
            sheets.append(self._build_drawdown_sheet(drawdown))

        if self._config.include_monthly_returns and monthly_returns:
            sheets.append(self._build_monthly_returns_sheet(monthly_returns))

        if self._config.include_trades and trades:
            sheets.append(self._build_trades_sheet(trades))

        if self._config.include_attribution and attribution:
            sheets.append(self._build_attribution_sheet(attribution))

        if self._config.include_sensitivity and sensitivity:
            sheets.append(self._build_sensitivity_sheet(sensitivity))

        return sheets

    def _build_metrics_sheet(self, metrics: dict[str, Any]) -> ExcelSheet:
        headers = ["Metric", "Value"]
        rows = []
        for key, value in metrics.items():
            display = f"{value:.4f}" if isinstance(value, float) else str(value)
            rows.append([str(key), display])
        return ExcelSheet(name="Metrics", headers=headers, rows=rows)

    def _build_equity_curve_sheet(self, equity_curve: list[dict[str, Any]]) -> ExcelSheet:
        headers = ["Date", "NAV", "Cash", "Positions Value", "Return %"]
        rows = []
        for point in equity_curve:
            rows.append(
                [
                    str(point.get("date", point.get("timestamp", ""))),
                    point.get("nav", 0.0),
                    point.get("cash", 0.0),
                    point.get("positions_value", 0.0),
                    point.get("return_pct", 0.0),
                ]
            )
        return ExcelSheet(name="Equity Curve", headers=headers, rows=rows)

    def _build_drawdown_sheet(self, drawdown: list[dict[str, Any]]) -> ExcelSheet:
        headers = ["Date", "Drawdown %", "Peak Value", "Trough Value", "Duration (days)"]
        rows = []
        for dd in drawdown:
            rows.append(
                [
                    str(dd.get("date", "")),
                    dd.get("drawdown_pct", 0.0),
                    dd.get("peak", 0.0),
                    dd.get("trough", 0.0),
                    dd.get("duration", 0),
                ]
            )
        return ExcelSheet(name="Drawdown", headers=headers, rows=rows)

    def _build_monthly_returns_sheet(self, monthly_returns: list[dict[str, Any]]) -> ExcelSheet:
        headers = ["Month", "Return %", "Cumulative %"]
        rows = []
        for mr in monthly_returns:
            rows.append(
                [
                    str(mr.get("month", "")),
                    mr.get("return_pct", 0.0),
                    mr.get("cumulative_pct", 0.0),
                ]
            )
        return ExcelSheet(name="Monthly Returns", headers=headers, rows=rows)

    def _build_trades_sheet(self, trades: list[dict[str, Any]]) -> ExcelSheet:
        headers = ["Date", "Instrument", "Side", "Quantity", "Price", "PnL", "Commission", "Reason"]
        rows = []
        for trade in trades:
            rows.append(
                [
                    str(trade.get("date", trade.get("timestamp", ""))),
                    trade.get("instrument_id", trade.get("symbol", "")),
                    trade.get("side", ""),
                    trade.get("quantity", 0),
                    trade.get("price", 0.0),
                    trade.get("pnl", 0.0),
                    trade.get("commission", 0.0),
                    trade.get("reason", ""),
                ]
            )
        return ExcelSheet(name="Trades", headers=headers, rows=rows)

    def _build_attribution_sheet(self, attribution: dict[str, Any]) -> ExcelSheet:
        headers = ["Factor", "Contribution %", "Exposure"]
        rows = []
        for factor, data in attribution.items():
            if isinstance(data, dict):
                rows.append(
                    [
                        str(factor),
                        data.get("contribution_pct", 0.0),
                        data.get("exposure", 0.0),
                    ]
                )
            else:
                rows.append([str(factor), data, ""])
        return ExcelSheet(name="Attribution", headers=headers, rows=rows)

    def _build_sensitivity_sheet(self, sensitivity: dict[str, Any]) -> ExcelSheet:
        headers = ["Parameter", "Base Value", "Low Impact", "High Impact", "Elasticity"]
        rows = []
        for param, data in sensitivity.items():
            if isinstance(data, dict):
                rows.append(
                    [
                        str(param),
                        data.get("base_value", 0.0),
                        data.get("low_impact", 0.0),
                        data.get("high_impact", 0.0),
                        data.get("elasticity", 0.0),
                    ]
                )
            else:
                rows.append([str(param), str(data), "", "", ""])
        return ExcelSheet(name="Sensitivity", headers=headers, rows=rows)
