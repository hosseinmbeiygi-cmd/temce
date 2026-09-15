from __future__ import annotations

from backtesting.signals.signal_models import Signal
from domain.common.enum_types import SignalType


class SignalConflictResolver:
    def __init__(self, strategy: str = "majority") -> None:
        self.strategy = strategy

    def resolve(self, signals: list[Signal]) -> Signal | None:
        if not signals:
            return None
        if self.strategy == "first":
            return signals[0]
        if self.strategy == "last":
            return signals[-1]
        if self.strategy == "strongest":
            return max(signals, key=lambda s: s.strength * s.confidence)
        if self.strategy == "most_confident":
            return max(signals, key=lambda s: s.confidence)
        if self.strategy == "majority":
            bullish = sum(1 for s in signals if s.signal_type in (SignalType.BULLISH, SignalType.STRONG_BUY))
            bearish = sum(1 for s in signals if s.signal_type in (SignalType.BEARISH, SignalType.STRONG_SELL))
            if bullish > bearish:
                return max(
                    (s for s in signals if s.signal_type in (SignalType.BULLISH, SignalType.STRONG_BUY)),
                    key=lambda s: s.confidence,
                    default=None,
                )
            elif bearish > bullish:
                return max(
                    (s for s in signals if s.signal_type in (SignalType.BEARISH, SignalType.STRONG_SELL)),
                    key=lambda s: s.confidence,
                    default=None,
                )
        return max(signals, key=lambda s: s.confidence)
