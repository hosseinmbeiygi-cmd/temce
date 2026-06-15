from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any


@dataclass
class TimeWindow:
    start: datetime
    end: datetime

    def __contains__(self, dt: datetime) -> bool:
        return self.start <= dt <= self.end

    def duration(self) -> timedelta:
        return self.end - self.start

    def overlap(self, other: TimeWindow) -> timedelta:
        latest_start = max(self.start, other.start)
        earliest_end = min(self.end, other.end)
        return max(timedelta(0), earliest_end - latest_start)

    def to_dict(self) -> dict[str, Any]:
        return {
            "start": self.start.isoformat(),
            "end": self.end.isoformat(),
        }


class SlidingTimeWindow:
    def __init__(self, duration: timedelta) -> None:
        self.duration = duration
        self._items: list[tuple[datetime, Any]] = []

    def add(self, item: Any, timestamp: datetime | None = None) -> None:
        ts = timestamp or datetime.now(UTC)
        self._items.append((ts, item))
        self._prune()

    def _prune(self) -> None:
        cutoff = datetime.now(UTC) - self.duration
        self._items = [(ts, item) for ts, item in self._items if ts > cutoff]

    @property
    def items(self) -> list[Any]:
        self._prune()
        return [item for _, item in self._items]

    @property
    def count(self) -> int:
        self._prune()
        return len(self._items)

    def clear(self) -> None:
        self._items.clear()
