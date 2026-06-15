from __future__ import annotations

from datetime import UTC

from domain.common.enum_types import SignalType


class SignalTypeRule:
    """Validate that signal type is a valid SignalType value."""

    def validate(self, signal_type: str) -> bool:
        return signal_type in {t.value for t in SignalType}


class StrengthRule:
    """Validate that strength is between 0 and 1."""

    def validate(self, strength: float) -> bool:
        return 0.0 <= strength <= 1.0


class DirectionRule:
    """Validate that direction is one of the allowed values."""

    def __init__(self) -> None:
        self.allowed_directions = {"up", "down", "sideways"}

    def validate(self, direction: str) -> bool:
        return direction in self.allowed_directions


class SourceRequiredRule:
    """Validate that source is not empty."""

    def validate(self, source: str) -> bool:
        return bool(source)


class ExpiryRule:
    """Validate that the signal hasn't expired."""

    def __init__(self, max_validity_hours: float = 48.0) -> None:
        self.max_validity_hours = max_validity_hours

    def validate(self, expires_at: str) -> bool:
        from datetime import datetime

        try:
            expiry = datetime.fromisoformat(expires_at)
            return expiry > datetime.now(UTC)
        except (ValueError, TypeError):
            return False


def validate_signal_score(score: float) -> bool:
    return 0.0 <= score <= 100.0


def validate_signal_confidence(confidence: float) -> bool:
    return 0.0 <= confidence <= 1.0


def validate_signal_strength(strength: float) -> bool:
    return 0.0 <= strength <= 1.0


def validate_signal_type(signal_type: str) -> bool:
    return signal_type in {t.value for t in SignalType}


def is_bullish_signal(signal_type: SignalType) -> bool:
    return signal_type in (SignalType.BULLISH, SignalType.STRONG_BUY)


def is_bearish_signal(signal_type: SignalType) -> bool:
    return signal_type in (SignalType.BEARISH, SignalType.STRONG_SELL)
