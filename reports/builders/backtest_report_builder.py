from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from core.logging import get_logger
from core.result import Result
from schemas.backtest.models import BacktestResultSchema

logger = get_logger(__name__)


class BacktestReportBuilder:
    async def build(self, result: BacktestResultSchema | dict[str, Any]) -> Result[dict[str, Any]]:
        data_in = result if isinstance(result, dict) else result.model_dump() if hasattr(result, "model_dump") else {}
        data: dict[str, Any] = {
            "title": f"Backtest Report: {data_in.get('strategy_name', 'N/A')}",
            "report_type": "backtest",
            "generated_at": datetime.now(UTC).isoformat(),
            "strategy_name": data_in.get("strategy_name", ""),
            "initial_capital": data_in.get("initial_capital", 0),
            "final_capital": data_in.get("final_capital", 0),
            "total_return": data_in.get("total_return", 0),
            "total_return_pct": data_in.get("total_return_pct", 0),
            "sharpe_ratio": data_in.get("sharpe_ratio", 0),
            "max_drawdown": data_in.get("max_drawdown", 0),
            "total_trades": data_in.get("total_trades", 0),
            "win_rate": data_in.get("win_rate", 0),
            "metrics": data_in.get("metrics", {}),
            "completed_at": str(data_in.get("completed_at", "")),
        }
        return Result.ok(data)
