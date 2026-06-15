from __future__ import annotations

import time
from typing import Any

from core.logging import get_logger

logger = get_logger(__name__)


class PrometheusExporter:
    def __init__(self):
        self._metrics: dict[str, Any] = {}
        self._counters: dict[str, float] = {}
        self._gauges: dict[str, float] = {}
        self._histograms: dict[str, list[float]] = {}
        self._enabled = True

    def counter(self, name: str, labels: dict[str, str] | None = None) -> float:
        key = self._metric_key(name, labels)
        self._counters.setdefault(key, 0.0)
        return self._counters[key]

    def inc(self, name: str, labels: dict[str, str] | None = None, value: float = 1.0) -> None:
        key = self._metric_key(name, labels)
        self._counters[key] = self._counters.get(key, 0.0) + value

    def gauge(self, name: str, labels: dict[str, str] | None = None) -> float:
        key = self._metric_key(name, labels)
        return self._gauges.get(key, 0.0)

    def set_gauge(self, name: str, value: float, labels: dict[str, str] | None = None) -> None:
        key = self._metric_key(name, labels)
        self._gauges[key] = value

    def observe(self, name: str, value: float, labels: dict[str, str] | None = None) -> None:
        key = self._metric_key(name, labels)
        if key not in self._histograms:
            self._histograms[key] = []
        self._histograms[key].append(value)

    def observe_duration(self, name: str, labels: dict[str, str] | None = None) -> _Timer:
        return _Timer(self, name, labels)

    def _metric_key(self, name: str, labels: dict[str, str] | None = None) -> str:
        if labels:
            label_str = ",".join(f"{k}={v}" for k, v in sorted(labels.items()))
            return f"{name}{{{label_str}}}"
        return name

    def export_text(self) -> str:
        lines: list[str] = []
        for key, value in self._counters.items():
            lines.append(f"# HELP {key} Counter metric")
            lines.append(f"# TYPE {key} counter")
            lines.append(f"{key} {value}")
        for key, value in self._gauges.items():
            lines.append(f"# HELP {key} Gauge metric")
            lines.append(f"# TYPE {key} gauge")
            lines.append(f"{key} {value}")
        for key, values in self._histograms.items():
            lines.append(f"# HELP {key} Histogram metric")
            lines.append(f"# TYPE {key} histogram")
            for v in values[-1000:]:
                lines.append(f'{key}_bucket{{le="+Inf"}} {v}')
            lines.append(f"{key}_count {len(values)}")
            lines.append(f"{key}_sum {sum(values)}")
        return "\n".join(lines)

    def disable(self) -> None:
        self._enabled = False

    def enable(self) -> None:
        self._enabled = True

    def reset(self) -> None:
        self._counters.clear()
        self._gauges.clear()
        self._histograms.clear()


class _Timer:
    def __init__(self, exporter: PrometheusExporter, name: str, labels: dict[str, str] | None = None):
        self._exporter = exporter
        self._name = name
        self._labels = labels
        self._start: float = 0.0

    def __enter__(self) -> _Timer:
        self._start = time.monotonic()
        return self

    def __exit__(self, *args: Any) -> None:
        duration = time.monotonic() - self._start
        self._exporter.observe(self._name, duration, self._labels)
