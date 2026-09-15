from __future__ import annotations

import json
import pickle
from typing import Any

from backtesting.types import BacktestResult
from core.paths import validate_safe_path


class Serializer:
    @staticmethod
    def to_dict(result: BacktestResult) -> dict[str, Any]:
        return {
            "strategy_name": result.strategy_name,
            "initial_capital": result.initial_capital,
            "final_capital": result.final_capital,
            "total_return": result.total_return,
            "total_return_pct": result.total_return_pct,
            "sharpe_ratio": result.sharpe_ratio,
            "max_drawdown": result.max_drawdown,
            "total_trades": result.total_trades,
            "win_rate": result.win_rate,
            "equity_curve": [
                {
                    "timestamp": p.timestamp.isoformat() if hasattr(p.timestamp, "isoformat") else str(p.timestamp),
                    "nav": p.nav,
                    "cash": p.cash,
                    "positions_value": p.positions_value,
                }
                for p in result.equity_curve
            ],
            "trades": [
                {
                    "order_id": t.order_id,
                    "instrument_id": t.instrument_id,
                    "side": t.side,
                    "quantity": t.quantity,
                    "price": t.price,
                    "commission": t.commission,
                    "timestamp": t.timestamp.isoformat() if hasattr(t.timestamp, "isoformat") else str(t.timestamp),
                }
                for t in result.trades
            ],
            "metrics": result.metrics,
            "metadata": result.metadata,
            "completed_at": result.completed_at.isoformat()
            if hasattr(result.completed_at, "isoformat")
            else str(result.completed_at),
        }

    @staticmethod
    def to_json(result: BacktestResult, indent: int = 2) -> str:
        return json.dumps(Serializer.to_dict(result), ensure_ascii=False, indent=indent)

    @staticmethod
    def to_pickle(result: BacktestResult) -> bytes:
        return pickle.dumps(result)

    @staticmethod
    def from_pickle(data: bytes) -> BacktestResult:
        return pickle.loads(data)

    @staticmethod
    def save_json(result: BacktestResult, filepath: str) -> None:
        safe = validate_safe_path(filepath)
        safe.write_text(Serializer.to_json(result), encoding="utf-8")

    @staticmethod
    def save_pickle(result: BacktestResult, filepath: str) -> None:
        safe = validate_safe_path(filepath)
        safe.write_bytes(Serializer.to_pickle(result))

    @staticmethod
    def load_json(filepath: str) -> dict[str, Any]:
        safe = validate_safe_path(filepath)
        return json.loads(safe.read_text(encoding="utf-8"))

    @staticmethod
    def load_pickle(filepath: str) -> BacktestResult:
        safe = validate_safe_path(filepath)
        return pickle.loads(safe.read_bytes())
