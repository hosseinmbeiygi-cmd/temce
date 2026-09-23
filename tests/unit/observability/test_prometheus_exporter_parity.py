"""Parity and bounded-memory guarantees for ``PrometheusExporter`` histograms.

The exporter previously stored histogram samples in an unbounded ``list``
(a slow RAM leak — one sample per HTTP request, kept forever) while the text
export only ever rendered ``values[-1000:]``. Storage is now a bounded
``deque(maxlen=1000)``. These tests pin:

1. **Parity** — the exported text is bit-for-bit identical to the frozen
   legacy reference implementation across randomized inputs (edge values
   included: 0.0, bucket boundaries, +inf-guarded NaN exclusion is upstream's
   concern; here raw finite floats).
2. **Boundedness** — after ``observe``ing far more than the window, the
   internal buffer stays capped at 1000 samples and the export matches the
   legacy window semantics (oldest evicted first).
3. **Contract** — counter/gauge/timer behaviour unchanged.
"""

from __future__ import annotations

import random
import re

import pytest

from integrations.observability.prometheus_exporter import (
    _HISTOGRAM_BUCKETS,
    PrometheusExporter,
)

_SAMPLE_LIMIT = 1000
# Legacy storage semantics, frozen verbatim from the pre-refactor module:
# unbounded list, export renders only the last 1000 samples.
_LEGACY_WINDOW = 1000


def _legacy_export_histograms(
    counters: dict[str, float],
    gauges: dict[str, float],
    histograms: dict[str, list[float]],
    buckets: tuple[float, ...],
) -> str:
    """Verbatim legacy export_text() histogram/counter/gauge rendering."""

    def _split_key(key: str) -> tuple[str, str]:
        brace = key.find("{")
        if brace == -1:
            return key, ""
        return key[:brace], key[brace:]

    def _render_series(lines: list[str], name: str, label_suffix: str, sample_suffix: str, value) -> None:
        labels = label_suffix
        if sample_suffix and labels:
            labels = labels[:-1] + f",{sample_suffix}" + labels[-1:]
        elif sample_suffix:
            labels = "{" + sample_suffix + "}"
        lines.append(f"{name}{labels} {value}")

    lines: list[str] = []
    for key, value in counters.items():
        name, labels = _split_key(key)
        lines.append(f"# HELP {name} Counter metric")
        lines.append(f"# TYPE {name} counter")
        lines.append(f"{name}{labels} {value}")
    for key, value in gauges.items():
        name, labels = _split_key(key)
        lines.append(f"# HELP {name} Gauge metric")
        lines.append(f"# TYPE {name} gauge")
        lines.append(f"{name}{labels} {value}")
    for key, values in histograms.items():
        name, labels = _split_key(key)
        lines.append(f"# HELP {name} Histogram metric")
        lines.append(f"# TYPE {name} histogram")
        counts = dict.fromkeys(buckets, 0)
        for v in values[-_LEGACY_WINDOW:]:
            for le in buckets:
                if v <= le:
                    counts[le] += 1
        for le, count in counts.items():
            _render_series(lines, name, labels, f'le="{le}"', count)
        _render_series(lines, name, labels, 'le="+Inf"', len(values[-_LEGACY_WINDOW:]))
        lines.append(f"{name}_count{labels} {len(values[-_LEGACY_WINDOW:])}")
        lines.append(f"{name}_sum{labels} {sum(values[-_LEGACY_WINDOW:])}")
    return "\n".join(lines)


def _collect_legacy(exporter: PrometheusExporter) -> tuple[dict[str, float], dict[str, float], dict[str, list[float]]]:
    """Rebuild legacy dicts from a live exporter for the reference renderer."""
    counters = dict(exporter._counters)
    gauges = dict(exporter._gauges)
    histograms = {k: list(v) for k, v in exporter._histograms.items()}
    return counters, gauges, histograms


class TestHistogramParity:
    def test_parity_with_legacy_reference_randomized(self) -> None:
        rng = random.Random(20260923)
        exp = PrometheusExporter()
        # Edge values around bucket boundaries + random durations.
        values = [0.0, 0.001, 0.005, 0.01, 0.05, 0.1, 0.5, 1.0, 5.0, 10.0, 30.0, 60.0, 999.0]
        values += [rng.random() * 70 for _ in range(500)]
        rng.shuffle(values)
        for v in values:
            exp.observe("http_request_duration_seconds", v, labels={"method": "GET", "route": "/x"})

        counters, gauges, hists = _collect_legacy(exp)
        legacy_text = _legacy_export_histograms(counters, gauges, hists, _HISTOGRAM_BUCKETS)
        assert exp.export_text() == legacy_text

    def test_parity_multiple_series_and_labels(self) -> None:
        exp = PrometheusExporter()
        exp.inc("http_requests_total", labels={"method": "GET", "route": "/a"})
        exp.inc("http_requests_total", labels={"method": "GET", "route": "/a"})
        exp.inc("http_requests_total", labels={"method": "POST", "route": "/b"})
        exp.set_gauge("heap_usage", 0.42)
        for i in range(50):
            exp.observe("latency_a", 0.01 * (i % 7))
            exp.observe("latency_b", 0.02 * (i % 5), labels={"route": "/b"})

        counters, gauges, hists = _collect_legacy(exp)
        legacy_text = _legacy_export_histograms(counters, gauges, hists, _HISTOGRAM_BUCKETS)
        assert exp.export_text() == legacy_text
        # NB: legacy _metric_key renders labels unquoted (method=GET,route=/a).
        assert 'http_requests_total{method=GET,route=/a} 2' in exp.export_text()

    def test_parity_at_exact_window_boundary(self) -> None:
        # Exactly _LEGACY_WINDOW samples: no eviction has happened yet on both
        # sides — the strongest bit-exactness point.
        rng = random.Random(42)
        exp = PrometheusExporter()
        for _ in range(_LEGACY_WINDOW):
            exp.observe("m", rng.random())
        counters, gauges, hists = _collect_legacy(exp)
        legacy_text = _legacy_export_histograms(counters, gauges, hists, _HISTOGRAM_BUCKETS)
        assert exp.export_text() == legacy_text

    def test_parity_over_window_eviction_order(self) -> None:
        # Push > window samples with a recognizable age pattern: the legacy
        # window drops the OLDEST samples; the deque must evict exactly the
        # same ones. Encode sample identity in the value.
        exp = PrometheusExporter()
        n = _LEGACY_WINDOW + 250
        for i in range(n):
            exp.observe("aged", float(i))
        counters, _, hists = _collect_legacy(exp)
        legacy_text = _legacy_export_histograms(counters, {}, hists, _HISTOGRAM_BUCKETS)
        assert exp.export_text() == legacy_text
        # And the surviving window must be the newest 1000 (250..1249).
        m = re.search(r"^aged_count(?:\{\})? (\d+)$", exp.export_text(), re.M)
        assert m and int(m.group(1)) == _LEGACY_WINDOW
        m = re.search(r"^aged_sum(?:\{\})? ([\d.]+)$", exp.export_text(), re.M)
        assert m and abs(float(m.group(1)) - sum(float(i) for i in range(250, n))) < 1e-6


class TestBoundedMemory:
    def test_buffer_never_exceeds_limit(self) -> None:
        exp = PrometheusExporter()
        for i in range(50_000):
            exp.observe("hot_series", float(i), labels={"route": "/hot"})
        assert len(exp._histograms['hot_series{route=/hot}']) == _SAMPLE_LIMIT

    def test_many_series_each_bounded(self) -> None:
        exp = PrometheusExporter()
        for s in range(100):
            for i in range(2_000):
                exp.observe(f"metric_{s}", float(i))
        assert all(len(v) == _SAMPLE_LIMIT for v in exp._histograms.values())

    def test_observe_duration_timer_still_records(self) -> None:
        exp = PrometheusExporter()
        with exp.observe_duration("route_latency", labels={"route": "/z"}):
            pass
        text = exp.export_text()
        assert 'le="+Inf"' in text
        assert re.search(r"route_latency_count\{route=/z\} 1", text)


class TestContractUnchanged:
    def test_counter_gauge_reset(self) -> None:
        exp = PrometheusExporter()
        exp.inc("c", value=2.5)
        exp.set_gauge("g", 7.0)
        assert exp.counter("c") == 2.5
        assert exp.gauge("g") == 7.0
        exp.reset()
        assert exp.export_text() == ""

    def test_disable_enable_flags(self) -> None:
        exp = PrometheusExporter()
        exp.disable()
        exp.enable()  # flags exist and are callable; exporter still functional
        exp.inc("after_enable")
        assert "after_enable" in exp.export_text()
