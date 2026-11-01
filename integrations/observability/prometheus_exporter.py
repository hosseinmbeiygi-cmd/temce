from __future__ import annotations

import json
import time
from collections import deque
from typing import Any

from core.logging import get_logger

logger = get_logger(__name__)

# Fixed histogram bucket boundaries (seconds). Kept deliberately small so
# the in-memory representation stays bounded and the text export is valid.
_HISTOGRAM_BUCKETS: tuple[float, ...] = (0.001, 0.005, 0.01, 0.05, 0.1, 0.5, 1.0, 5.0, 10.0, 30.0, 60.0)

# Per-series histogram samples are kept in a bounded circular buffer of exactly
# this size — the same window the text export has always rendered (values[-1000:]).
# The middleware observes one sample per HTTP request, so an unbounded list here
# grew linearly with traffic for the lifetime of the process (slow RAM leak).
_HISTOGRAM_SAMPLE_LIMIT = 1000


class PrometheusExporter:
    def __init__(self) -> None:
        self._metrics: dict[str, Any] = {}
        self._counters: dict[str, float] = {}
        self._gauges: dict[str, float] = {}
        self._histograms: dict[str, deque[float]] = {}
        # Structured label values per series key. The legacy ``export_text``
        # renders unquoted labels from the key string; the Prometheus-valid
        # renderer needs the original values without parsing them back.
        self._series_labels: dict[str, dict[str, str]] = {}
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
        buf = self._histograms.get(key)
        if buf is None:
            buf = self._histograms[key] = deque(maxlen=_HISTOGRAM_SAMPLE_LIMIT)
        buf.append(value)  # oldest sample is evicted automatically at maxlen

    def observe_duration(self, name: str, labels: dict[str, str] | None = None) -> _Timer:
        return _Timer(self, name, labels)

    def _metric_key(self, name: str, labels: dict[str, str] | None = None) -> str:
        """Storage key only — labels are kept separately for rendering."""
        if labels:
            label_str = ",".join(f"{k}={v}" for k, v in sorted(labels.items()))
            key = f"{name}{{{label_str}}}"
            self._series_labels[key] = {str(k): str(v) for k, v in labels.items()}
            return key
        self._series_labels.setdefault(name, {})
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
        """Legacy renderer (unquoted labels) kept for compatibility/parity tests.

        Use :meth:`export_prometheus` for anything a Prometheus server will
        scrape: this legacy output is not valid exposition format once labels
        are present.
        """
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
            # The deque is bounded at _HISTOGRAM_SAMPLE_LIMIT, so this equals
            # the legacy `values[-1000:]` window bit-for-bit.
            samples = tuple(values)
            # Cumulative bucket counts (valid Prometheus text format).
            counts = dict.fromkeys(_HISTOGRAM_BUCKETS, 0)
            for v in samples:
                for le in _HISTOGRAM_BUCKETS:
                    if v <= le:
                        counts[le] += 1
            for le, count in counts.items():
                self._render_series(lines, name, labels, f'le="{le}"', count)
            self._render_series(lines, name, labels, 'le="+Inf"', len(samples))
            lines.append(f"{name}_count{labels} {len(samples)}")
            lines.append(f"{name}_sum{labels} {sum(samples)}")
        return "\n".join(lines)

    # ── Prometheus-valid exposition ───────────────────────────────────────
    # ``export_text`` predates label quoting and repeats HELP/TYPE per series;
    # a real Prometheus parser rejects both. This renderer emits one HELP/TYPE
    # per family and Go-quoted label values, so ``/metrics`` is scrapeable.

    def export_prometheus(self) -> str:
        lines: list[str] = []
        lines.extend(self._render_scalar_family(self._counters, "counter"))
        lines.extend(self._render_scalar_family(self._gauges, "gauge"))
        lines.extend(self._render_histogram_families())
        return "\n".join(lines)

    def _render_scalar_family(self, store: dict[str, float], kind: str) -> list[str]:
        by_name: dict[str, list[tuple[str, float]]] = {}
        for key, value in store.items():
            name, _ = self._split_key(key)
            by_name.setdefault(name, []).append((key, value))

        lines: list[str] = []
        for name, series in by_name.items():
            lines.append(f"# HELP {name} {kind.capitalize()} metric")
            lines.append(f"# TYPE {name} {kind}")
            for key, value in series:
                lines.append(f"{name}{self._labels_text(key)} {value}")
        return lines

    def _render_histogram_families(self) -> list[str]:
        by_name: dict[str, list[tuple[str, deque[float]]]] = {}
        for key, values in self._histograms.items():
            name, _ = self._split_key(key)
            by_name.setdefault(name, []).append((key, values))

        lines: list[str] = []
        for name, series in by_name.items():
            lines.append(f"# HELP {name} Histogram metric")
            lines.append(f"# TYPE {name} histogram")
            for key, values in series:
                samples = tuple(values)
                counts = dict.fromkeys(_HISTOGRAM_BUCKETS, 0)
                for value in samples:
                    for le in _HISTOGRAM_BUCKETS:
                        if value <= le:
                            counts[le] += 1
                for le, count in counts.items():
                    lines.append(f"{name}_bucket{self._labels_text(key, ('le', str(le)))} {count}")
                lines.append(f"{name}_bucket{self._labels_text(key, ('le', '+Inf'))} {len(samples)}")
                lines.append(f"{name}_count{self._labels_text(key)} {len(samples)}")
                lines.append(f"{name}_sum{self._labels_text(key)} {sum(samples)}")
        return lines

    def _labels_text(self, key: str, extra: tuple[str, str] | None = None) -> str:
        labels = dict(self._series_labels.get(key, {}))
        if extra is not None:
            labels[extra[0]] = extra[1]
        if not labels:
            return ""
        rendered = ",".join(
            f"{name}={json.dumps(value, ensure_ascii=False)}"
            for name, value in sorted(labels.items())
        )
        return "{" + rendered + "}"

    def disable(self) -> None:
        self._enabled = False

    def enable(self) -> None:
        self._enabled = True

    def reset(self) -> None:
        self._counters.clear()
        self._gauges.clear()
        self._histograms.clear()
        self._series_labels.clear()


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
