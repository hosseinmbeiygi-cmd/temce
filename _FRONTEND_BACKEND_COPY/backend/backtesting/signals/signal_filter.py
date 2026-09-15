from __future__ import annotations

from collections.abc import Callable

from backtesting.signals.signal_models import Signal


class SignalFilter:
    def __init__(self) -> None:
        self._filters: list[Callable[[Signal], bool]] = []

    def add_filter(self, filter_fn: Callable[[Signal], bool]) -> None:
        self._filters.append(filter_fn)

    def apply(self, signals: list[Signal]) -> list[Signal]:
        filtered = signals
        for f in self._filters:
            filtered = [s for s in filtered if f(s)]
        return filtered

    def strength_filter(self, min_strength: float = 0.5) -> Callable[[Signal], bool]:
        return lambda s: s.strength >= min_strength

    def confidence_filter(self, min_confidence: float = 0.3) -> Callable[[Signal], bool]:
        return lambda s: s.confidence >= min_confidence

    def source_filter(self, source: str) -> Callable[[Signal], bool]:
        return lambda s: s.source == source

    def clear(self) -> None:
        self._filters.clear()
