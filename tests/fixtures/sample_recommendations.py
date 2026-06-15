from __future__ import annotations

from core.ids import new_id
from domain.analytics.recommendation import Recommendation
from domain.common.enum_types import RecommendationAction


def sample_recommendation(
    id: str | None = None,
    symbol: str = "فولاد",
    action: str = "buy",
) -> Recommendation:
    return Recommendation(
        id=id or new_id("rec"),
        instrument_id="inst_test_001",
        action=RecommendationAction(action),
        symbol=symbol,
        target_price=18000.0,
        confidence=0.82,
        horizon="medium_term",
        rationale="تحلیل بنیادی قوی با P/E مناسب و رشد سودآوری",
        source="system",
        extra={
            "stop_loss": 14000.0,
            "strategy": "value",
            "risk_level": "moderate",
        },
    )


def sample_recommendation_list(count: int = 5) -> list[Recommendation]:
    actions = ["buy", "sell", "hold", "accumulate", "reduce"]
    symbols = ["فولاد", "فملی", "وبانک", "کگل", "خودرو"]
    return [
        sample_recommendation(
            symbol=symbols[i % len(symbols)],
            action=actions[i % len(actions)],
        )
        for i in range(count)
    ]
