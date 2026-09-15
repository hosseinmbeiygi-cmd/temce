from __future__ import annotations

import time
from datetime import UTC, datetime
from typing import Any


class MetricsCollector:
    def __init__(self) -> None:
        self._counters: dict[str, int] = {}
        self._gauges: dict[str, float] = {}
        self._histograms: dict[str, list[float]] = {}

    def increment(self, name: str, value: int = 1) -> None:
        self._counters[name] = self._counters.get(name, 0) + value

    def gauge(self, name: str, value: float) -> None:
        self._gauges[name] = value

    def observe(self, name: str, value: float) -> None:
        if name not in self._histograms:
            self._histograms[name] = []
        self._histograms[name].append(value)

    def timed(self, name: str) -> Timer:
        return Timer(self, name)

    def snapshot(self) -> dict[str, Any]:
        return {
            "counters": dict(self._counters),
            "gauges": dict(self._gauges),
            "histograms": {
                k: {"count": len(v), "sum": sum(v), "avg": sum(v) / len(v) if v else 0}
                for k, v in self._histograms.items()
            },
            "timestamp": datetime.now(UTC).isoformat(),
        }

    def reset(self) -> None:
        self._counters.clear()
        self._gauges.clear()
        self._histograms.clear()


class Timer:
    def __init__(self, collector: MetricsCollector, name: str) -> None:
        self.collector = collector
        self.name = name
        self.start: float = 0.0

    def __enter__(self) -> Timer:
        self.start = time.monotonic()
        return self

    def __exit__(self, *args: Any) -> None:
        elapsed = (time.monotonic() - self.start) * 1000
        self.collector.observe(self.name, elapsed)


metrics_collector = MetricsCollector()
