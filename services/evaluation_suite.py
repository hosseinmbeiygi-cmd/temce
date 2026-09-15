"""M3: Shared EvaluationSuite — common metrics for backtest + ML + screener.

Replaces duplicated metric logic in:
- backtesting/metrics/*
- ml/metrics.py
- services/screener110_service.py (scoring)
- services/fund_scoring.py

Provides a single `evaluate()` entry point returning a normalized dict so
results from different engines are directly comparable (mirrors BacktestRunner
parity guard).
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any

import numpy as np


@dataclass
class EvaluationResult:
    accuracy: float = 0.0
    precision: float = 0.0
    recall: float = 0.0
    f1: float = 0.0
    sharpe: float = 0.0
    max_drawdown: float = 0.0
    win_rate: float = 0.0
    profit_factor: float = 0.0
    extra: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "accuracy": round(self.accuracy, 4),
            "precision": round(self.precision, 4),
            "recall": round(self.recall, 4),
            "f1": round(self.f1, 4),
            "sharpe": round(self.sharpe, 4),
            "max_drawdown": round(self.max_drawdown, 4),
            "win_rate": round(self.win_rate, 4),
            "profit_factor": round(self.profit_factor, 4),
            "extra": self.extra,
        }


def _safe_div(a: float, b: float) -> float:
    return a / b if b else 0.0


class EvaluationSuite:
    """Unified metrics — use for backtest trades, ML predictions, or screener signals."""

    @staticmethod
    def classification(y_true: list[int] | np.ndarray, y_pred: list[int] | np.ndarray) -> EvaluationResult:
        y_true = np.asarray(y_true, dtype=int)
        y_pred = np.asarray(y_pred, dtype=int)
        tp = int(np.sum((y_true == 1) & (y_pred == 1)))
        tn = int(np.sum((y_true == 0) & (y_pred == 0)))
        fp = int(np.sum((y_true == 0) & (y_pred == 1)))
        fn = int(np.sum((y_true == 1) & (y_pred == 0)))
        total = len(y_true) or 1
        accuracy = (tp + tn) / total
        precision = _safe_div(tp, tp + fp)
        recall = _safe_div(tp, tp + fn)
        f1 = _safe_div(2 * precision * recall, precision + recall)
        return EvaluationResult(accuracy=accuracy, precision=precision, recall=recall, f1=f1, extra={"tp": tp, "tn": tn, "fp": fp, "fn": fn})

    @staticmethod
    def trading(returns: list[float] | np.ndarray) -> EvaluationResult:
        arr = np.asarray(returns, dtype=float)
        if arr.size == 0:
            return EvaluationResult()
        mean = float(np.mean(arr))
        std = float(np.std(arr)) or 1e-9
        sharpe = mean / std * math.sqrt(252)
        # Max drawdown from cumulative returns
        cum = np.cumsum(arr)
        peak = np.maximum.accumulate(cum)
        dd = peak - cum
        max_dd = float(np.max(dd)) if dd.size else 0.0
        wins = int(np.sum(arr > 0))
        win_rate = wins / arr.size
        gross_profit = float(np.sum(arr[arr > 0]))
        gross_loss = abs(float(np.sum(arr[arr < 0]))) or 1e-9
        pf = gross_profit / gross_loss
        return EvaluationResult(sharpe=sharpe, max_drawdown=max_dd, win_rate=win_rate, profit_factor=pf, extra={"mean_return": mean, "trades": int(arr.size)})

    @staticmethod
    def evaluate(kind: str, **kwargs: Any) -> EvaluationResult:
        if kind == "classification":
            return EvaluationSuite.classification(kwargs["y_true"], kwargs["y_pred"])
        if kind == "trading":
            return EvaluationSuite.trading(kwargs["returns"])
        raise ValueError(f"Unknown evaluation kind: {kind}")
