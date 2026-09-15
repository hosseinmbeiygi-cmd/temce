from __future__ import annotations

import json
from datetime import datetime

from backtesting.reporting.equity_curve import EquityCurveReport
from backtesting.reporting.summary_report import SummaryReport
from backtesting.reporting.trade_log_report import TradeLogReport
from backtesting.types import BacktestResult
from core.paths import validate_safe_path


class JSONReport:
    @staticmethod
    def generate(result: BacktestResult) -> str:
        summary = SummaryReport.generate(result)
        equity = EquityCurveReport.generate(result)
        trades = TradeLogReport.generate(result)
        report = {
            "summary": summary,
            "equity_curve": equity,
            "trades": trades,
            "generated_at": datetime.now().isoformat(),
        }
        return json.dumps(report, ensure_ascii=False, indent=2)

    @staticmethod
    def save(result: BacktestResult, filepath: str) -> None:
        safe = validate_safe_path(filepath)
        data = JSONReport.generate(result)
        safe.write_text(data, encoding="utf-8")
