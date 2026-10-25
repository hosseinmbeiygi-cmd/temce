from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class SymbolAssessmentSnapshotOut:
    symbol: str
    market_metrics: dict[str, Any] = field(default_factory=dict)
    ml_prediction: dict[str, Any] = field(default_factory=dict)
    backtest_summary: dict[str, Any] = field(default_factory=dict)
    codal_signals: dict[str, Any] = field(default_factory=dict)
    decision_summary: dict[str, Any] = field(default_factory=dict)
    last_evaluated_at: str = ""

@dataclass
class SymbolAssessmentTask:
    symbol: str
    market: str
    user_id: str
