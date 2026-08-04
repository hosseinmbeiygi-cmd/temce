from __future__ import annotations

import time
from typing import Any

from core.logging import get_logger

logger = get_logger(__name__)

# Fixed histogram bucket boundaries (seconds). Kept deliberately small so
# the in-memory representation stays bounded and the text export is valid.
_HISTOGRAM_BUCKETS: tuple[float, ...] = (0.001, 0.005, 0.01, 0.05, 0.1, 0.5, 1.0, 5.0, 10.0, 30.0, 60.0)


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
        """Storage key only — labels are kept separately for rendering."""
        if labels:
            label_str = ",".join(f"{k}={v}" for k, v in sorted(labels.items()))
            return f"{name}{{{label_str}}}"
        return name

    def _split_key(self, key: str) -> tuple[str, str]:
        """Split a storage key back into (metric name, label suffix)."""
        brace = key.find("{")
        if brace == -1:
            return key, ""
        return key[:brace], key[brace:]

    def _render_series(
        self,
        lines: list[str],
        metric_name: str,
        label_suffix: str,
        sample_suffix: str,
        value: float | int | str,
    ) -> None:
        """Emit one sample: ``name{suffix}`` with labels placed correctly."""
        labels = label_suffix
        if sample_suffix and labels:
            # e.g. name_bucket{le="1.0",k="v"}
            labels = labels[:-1] + f",{sample_suffix}" + labels[-1:]
        elif sample_suffix:
            labels = "{" + sample_suffix + "}"
        lines.append(f"{metric_name}{labels} {value}")

    def export_text(self) -> str:
        lines: list[str] = []
        for key, value in self._counters.items():
            name, labels = self._split_key(key)
            lines.append(f"# HELP {name} Counter metric")
            lines.append(f"# TYPE {name} counter")
            lines.append(f"{name}{labels} {value}")
        for key, value in self._gauges.items():
            name, labels = self._split_key(key)
            lines.append(f"# HELP {name} Gauge metric")
            lines.append(f"# TYPE {name} gauge")
            lines.append(f"{name}{labels} {value}")
        for key, values in self._histograms.items():
            name, labels = self._split_key(key)
            lines.append(f"# HELP {name} Histogram metric")
            lines.append(f"# TYPE {name} histogram")
            # Cumulative bucket counts (valid Prometheus text format).
            counts = dict.fromkeys(_HISTOGRAM_BUCKETS, 0)
            for v in values[-1000:]:
                for le in _HISTOGRAM_BUCKETS:
                    if v <= le:
                        counts[le] += 1
            for le, count in counts.items():
                self._render_series(lines, name, labels, f'le="{le}"', count)
            self._render_series(lines, name, labels, 'le="+Inf"', len(values[-1000:]))
            lines.append(f"{name}_count{labels} {len(values[-1000:])}")
            lines.append(f"{name}_sum{labels} {sum(values[-1000:])}")
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
