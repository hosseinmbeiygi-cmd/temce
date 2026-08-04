"""Signal accuracy tracking models — store signal outcomes and compute accuracy metrics."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import DateTime, Float, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from models.base import Base, TimestampMixin


class SignalAccuracyModel(TimestampMixin, Base):
    """Tracks the actual outcome of each generated signal — used to compute hit-rate by market/source."""

    __tablename__ = "signal_accuracy"

    id: Mapped[str] = mapped_column(String(50), primary_key=True)
    signal_id: Mapped[str | None] = mapped_column(String(50), index=True)
    symbol: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    market: Mapped[str] = mapped_column(String(30), nullable=False, index=True)  # stock / gold / currency / crypto / option / commodity / ime
    source: Mapped[str] = mapped_column(String(100), index=True)  # rule_based / ml_model_name / ensemble
    direction: Mapped[str] = mapped_column(String(10))  # buy / sell / hold
    timeframe: Mapped[str] = mapped_column(String(10), server_default="daily")

    # Outcome — set after the prediction period ends
    actual_return_pct: Mapped[float | None] = mapped_column(Float)
    direction_correct: Mapped[bool | None] = mapped_column(index=True)
    max_profit_pct: Mapped[float | None] = mapped_column(Float)
    max_loss_pct: Mapped[float | None] = mapped_column(Float)
    hit_target1: Mapped[bool | None] = mapped_column(default=False)
    hit_target2: Mapped[bool | None] = mapped_column(default=False)
    stopped_out: Mapped[bool | None] = mapped_column(default=False)

    # Metadata
    entry_price: Mapped[float | None] = mapped_column(Float)
    exit_price: Mapped[float | None] = mapped_column(Float)
    signal_price: Mapped[float | None] = mapped_column(Float)
    signal_strength: Mapped[float | None] = mapped_column(Float)
    signal_confidence: Mapped[float | None] = mapped_column(Float)
    ml_score: Mapped[float | None] = mapped_column(Float)  # ML model's prediction score if applicable
    rule_score: Mapped[float | None] = mapped_column(Float)  # Rule-based score if applicable

    generated_at: Mapped[datetime | None] = mapped_column(DateTime, server_default=func.now())
    outcome_set_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    notes: Mapped[str | None] = mapped_column(Text)


class SignalAccuracyResult:
    """Computes and holds accuracy metrics for a set of signals."""

    def __init__(self, records: list[dict[str, Any]]) -> None:
        self.records = records
        self._compute()

    def _compute(self) -> None:
        total = len(self.records)
        correct = sum(1 for r in self.records if r.get("direction_correct"))
        buy_signals = [r for r in self.records if r.get("direction") == "buy"]
        sell_signals = [r for r in self.records if r.get("direction") == "sell"]
        hold_signals = [r for r in self.records if r.get("direction") == "hold"]

        self.total = total
        self.correct = correct
        self.accuracy = correct / max(total, 1)

        self.buy_accuracy = sum(1 for r in buy_signals if r.get("direction_correct")) / max(len(buy_signals), 1)
        self.sell_accuracy = sum(1 for r in sell_signals if r.get("direction_correct")) / max(len(sell_signals), 1)
        self.hold_accuracy = sum(1 for r in hold_signals if r.get("direction_correct")) / max(len(hold_signals), 1)

        self.avg_return = sum(r.get("actual_return_pct") or 0 for r in self.records) / max(total, 1)
        self.avg_max_profit = sum(r.get("max_profit_pct") or 0 for r in self.records) / max(total, 1)
        self.avg_max_loss = sum(r.get("max_loss_pct") or 0 for r in self.records) / max(total, 1)
        self.target1_hit_rate = sum(1 for r in self.records if r.get("hit_target1")) / max(total, 1)
        self.stop_out_rate = sum(1 for r in self.records if r.get("stopped_out")) / max(total, 1)

        # Sharpe-like metric: avg_return / std(returns)
        returns = [r.get("actual_return_pct") or 0 for r in self.records]
        mean_r = sum(returns) / max(len(returns), 1)
        var_r = sum((r - mean_r) ** 2 for r in returns) / max(len(returns), 1)
        self.sharpe = mean_r / max(var_r ** 0.5, 0.001)

        # Profit factor: sum(profits) / sum(losses)
        total_profit = sum(max(r.get("actual_return_pct") or 0, 0) for r in self.records)
        total_loss = sum(abs(min(r.get("actual_return_pct") or 0, 0)) for r in self.records)
        self.profit_factor = total_profit / max(total_loss, 0.001)

    def to_dict(self) -> dict[str, Any]:
        return {
            "total_signals": self.total,
            "correct_predictions": self.correct,
            "accuracy_pct": round(self.accuracy * 100, 2),
            "buy_accuracy_pct": round(self.buy_accuracy * 100, 2),
            "sell_accuracy_pct": round(self.sell_accuracy * 100, 2),
            "hold_accuracy_pct": round(self.hold_accuracy * 100, 2),
            "avg_return_pct": round(self.avg_return, 2),
            "avg_max_profit_pct": round(self.avg_max_profit, 2),
            "avg_max_loss_pct": round(self.avg_max_loss, 2),
            "target1_hit_rate_pct": round(self.target1_hit_rate * 100, 2),
            "stop_out_rate_pct": round(self.stop_out_rate * 100, 2),
            "sharpe": round(self.sharpe, 3),
            "profit_factor": round(self.profit_factor, 2),
        }
