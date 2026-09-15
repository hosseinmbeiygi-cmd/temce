from __future__ import annotations

from domain.common.enum_types import RecommendationAction


class ActionRule:
    """Validate that the action is a valid recommendation action."""

    def validate(self, action: str) -> bool:
        return action in {a.value for a in RecommendationAction}


class ConfidenceRule:
    """Validate that confidence is between 0 and 1."""

    def validate(self, confidence: float) -> bool:
        return 0.0 <= confidence <= 1.0


class RiskLevelRule:
    """Validate that risk level is one of the allowed values."""

    def __init__(self) -> None:
        self.allowed_risk_levels = {"low", "moderate", "high"}

    def validate(self, risk_level: str) -> bool:
        return risk_level in self.allowed_risk_levels


class HorizonRule:
    """Validate that horizon is one of the allowed values."""

    def __init__(self) -> None:
        self.allowed_horizons = {"short_term", "medium_term", "long_term"}

    def validate(self, horizon: str) -> bool:
        return horizon in self.allowed_horizons


class TargetPriceRule:
    """Validate that target price is positive."""

    def validate(self, target_price: float, current_price: float) -> bool:
        return target_price > 0


def validate_recommendation_action(action: str) -> bool:
    return action in {a.value for a in RecommendationAction}


def validate_confidence(confidence: float) -> bool:
    return 0.0 <= confidence <= 1.0


def validate_score(score: float) -> bool:
    return 0.0 <= score <= 100.0


def is_buy_action(action: RecommendationAction) -> bool:
    return action in (RecommendationAction.BUY, RecommendationAction.ACCUMULATE)


def is_sell_action(action: RecommendationAction) -> bool:
    return action in (RecommendationAction.SELL, RecommendationAction.REDUCE)


def is_action_upgrade(previous: str, current: str) -> bool:
    ordering = ["sell", "reduce", "hold", "accumulate", "buy"]
    if previous not in ordering or current not in ordering:
        return False
    return ordering.index(current) > ordering.index(previous)
