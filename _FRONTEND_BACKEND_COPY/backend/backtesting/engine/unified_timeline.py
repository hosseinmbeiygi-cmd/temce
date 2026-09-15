from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from backtesting.engine.event_builder import MarketEvent


@dataclass
class TimelineStats:
    total_events: int = 0
    event_counts: dict[str, int] = field(default_factory=dict)
    instrument_counts: dict[str, int] = field(default_factory=dict)
    market_counts: dict[str, int] = field(default_factory=dict)
    time_span_start: datetime | None = None
    time_span_end: datetime | None = None


class UnifiedTimeline:
    def __init__(self) -> None:
        self._events: list[MarketEvent] = []
        self._sorted = True

    def add_event(self, event: MarketEvent) -> None:
        self._events.append(event)
        self._sorted = False

    def add_events(self, events: list[MarketEvent]) -> None:
        self._events.extend(events)
        self._sorted = False

    def _ensure_sorted(self) -> None:
        if not self._sorted:
            self._events.sort(key=lambda e: (e.timestamp, e.priority))
            self._sorted = True

    def __iter__(self) -> Any:
        self._ensure_sorted()
        return iter(self._events)

    def __len__(self) -> int:
        return len(self._events)

    def stream(self, batch_size: int = 1000) -> Any:
        self._ensure_sorted()
        for i in range(0, len(self._events), batch_size):
            yield self._events[i : i + batch_size]

    def filter_by_instrument(self, instrument_id: str) -> UnifiedTimeline:
        result = UnifiedTimeline()
        result._events = [e for e in self._events if e.instrument_id == instrument_id]
        result._sorted = self._sorted
        return result

    def filter_by_market(self, market_id: str) -> UnifiedTimeline:
        result = UnifiedTimeline()
        result._events = [e for e in self._events if e.market_id == market_id]
        result._sorted = self._sorted
        return result

    def filter_by_type(self, event_type: str) -> UnifiedTimeline:
        result = UnifiedTimeline()
        result._events = [e for e in self._events if e.event_type == event_type]
        result._sorted = self._sorted
        return result

    def filter_by_time_range(self, start: datetime, end: datetime) -> UnifiedTimeline:
        result = UnifiedTimeline()
        result._events = [e for e in self._events if start <= e.timestamp <= end]
        result._sorted = self._sorted
        return result

    def get_stats(self) -> TimelineStats:
        self._ensure_sorted()
        stats = TimelineStats(total_events=len(self._events))
        for event in self._events:
            et = str(event.event_type)
            stats.event_counts[et] = stats.event_counts.get(et, 0) + 1
            stats.instrument_counts[event.instrument_id] = stats.instrument_counts.get(event.instrument_id, 0) + 1
            stats.market_counts[event.market_id] = stats.market_counts.get(event.market_id, 0) + 1
        if self._events:
            stats.time_span_start = self._events[0].timestamp
            stats.time_span_end = self._events[-1].timestamp
        return stats

    def clear(self) -> None:
        self._events.clear()
        self._sorted = True
