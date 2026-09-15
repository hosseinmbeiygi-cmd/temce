from __future__ import annotations

from enum import StrEnum


class SignalDirection(StrEnum):
    BULLISH = "bullish"
    BEARISH = "bearish"
    NEUTRAL = "neutral"


class SignalStrength(StrEnum):
    WEAK = "weak"
    MODERATE = "moderate"
    STRONG = "strong"
    VERY_STRONG = "very_strong"


class SignalCategory(StrEnum):
    TREND = "trend"
    MOMENTUM = "momentum"
    VOLATILITY = "volatility"
    VOLUME = "volume"
    PATTERN = "pattern"
    DIVERGENCE = "divergence"
    CROSSOVER = "crossover"
    SUPPORT_RESISTANCE = "support_resistance"


class SignalStatus(StrEnum):
    ACTIVE = "active"
    CONFIRMED = "confirmed"
    EXPIRED = "expired"
    INVALIDATED = "invalidated"
