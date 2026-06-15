from __future__ import annotations

from enum import StrEnum


class RecommendationStrength(StrEnum):
    STRONG_BUY = "strong_buy"
    BUY = "buy"
    ACCUMULATE = "accumulate"
    HOLD = "hold"
    REDUCE = "reduce"
    SELL = "sell"
    STRONG_SELL = "strong_sell"


class RecommendationSource(StrEnum):
    TECHNICAL = "technical"
    FUNDAMENTAL = "fundamental"
    SENTIMENT = "sentiment"
    ML_MODEL = "ml_model"
    HYBRID = "hybrid"
    MANUAL = "manual"


class RecommendationStatus(StrEnum):
    ACTIVE = "active"
    EXPIRED = "expired"
    SUPERSEDED = "superseded"
    CANCELLED = "cancelled"


class RiskLevel(StrEnum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    VERY_HIGH = "very_high"
