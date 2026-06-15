from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class DecisionMatrix:
    scores: dict[str, float] = field(default_factory=dict)
    weights: dict[str, float] = field(default_factory=dict)
    thresholds: dict[str, float] = field(default_factory=dict)
    final_score: float = 0.0
    decision: str = "hold"
    metadata: dict[str, Any] = field(default_factory=dict)

    def compute(self) -> None:
        total = 0.0
        weight_sum = 0.0
        for key, score in self.scores.items():
            w = self.weights.get(key, 1.0)
            total += score * w
            weight_sum += w
        self.final_score = total / weight_sum if weight_sum > 0 else 0.0

        if self.final_score >= self.thresholds.get("strong_buy", 80):
            self.decision = "buy"
        elif self.final_score >= self.thresholds.get("buy", 60):
            self.decision = "accumulate"
        elif self.final_score <= self.thresholds.get("strong_sell", 20):
            self.decision = "sell"
        elif self.final_score <= self.thresholds.get("sell", 40):
            self.decision = "reduce"
        else:
            self.decision = "hold"
