from __future__ import annotations

from backtesting.signals.signal_models import Signal


class SignalPriority:
    def __init__(self) -> None:
        self._priority_map: dict[str, int] = {}

    def set_priority(self, source: str, priority: int) -> None:
        self._priority_map[source] = priority

    def get_priority(self, source: str) -> int:
        return self._priority_map.get(source, 0)

    def sort(self, signals: list[Signal]) -> list[Signal]:
        return sorted(signals, key=lambda s: self._priority_map.get(s.source, 0), reverse=True)

    def clear(self) -> None:
        self._priority_map.clear()
