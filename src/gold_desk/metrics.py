"""Prometheus metrics برای GoldDesk — endpoint /metrics.

expose counters + histograms برای monitoring:
- snapshot_build_seconds: زمان ساخت snapshot
- signal_total: تعداد signalهای live
- alert_fired_total: alertهای fired
- backtest_seconds: زمان backtest
- chat_total: تعداد پرسش‌های chat
- ws_clients: تعداد subscriberها
"""

from __future__ import annotations

import time
from collections.abc import Iterator
from contextlib import contextmanager

# ── Counters ─────────────────────────────────────────────────

snapshot_total = 0
signal_total = 0
alert_fired_total = 0
chat_total = 0
api_errors_total = 0

# ── Histograms (seconds) ───────────────────────────────────

_snapshot_durations: list[float] = []
_backtest_durations: list[float] = []
_dca_durations: list[float] = []


@contextmanager
def measure_snapshot() -> Iterator[None]:
    start = time.monotonic()
    yield
    _snapshot_durations.append(time.monotonic() - start)


@contextmanager
def measure_backtest() -> Iterator[None]:
    start = time.monotonic()
    yield
    _backtest_durations.append(time.monotonic() - start)


@contextmanager
def measure_dca() -> Iterator[None]:
    start = time.monotonic()
    yield
    _dca_durations.append(time.monotonic() - start)


# ── WS clients ──────────────────────────────────────────────


def ws_client_count() -> int:
    try:
        from .ws_hub import get_hub

        return get_hub().client_count()
    except Exception:
        return 0


# ── Render ──────────────────────────────────────────────────


def _percentile(values: list[float], p: float) -> float:
    if not values:
        return 0.0
    sorted_v = sorted(values)
    idx = int(len(sorted_v) * p)
    return sorted_v[min(idx, len(sorted_v) - 1)]


def render_prometheus() -> str:
    """رندر همه metrics به فرمت Prometheus text."""
    lines: list[str] = []

    # Counters
    lines.append("# HELP golddesk_snapshots_total Total snapshots built")
    lines.append("# TYPE golddesk_snapshots_total counter")
    lines.append(f"golddesk_snapshots_total {snapshot_total}")

    lines.append("# HELP golddesk_signals_total Total live signals detected")
    lines.append("# TYPE golddesk_signals_total counter")
    lines.append(f"golddesk_signals_total {signal_total}")

    lines.append("# HELP golddesk_alerts_fired_total Total alert events fired")
    lines.append("# TYPE golddesk_alerts_fired_total counter")
    lines.append(f"golddesk_alerts_fired_total {alert_fired_total}")

    lines.append("# HELP golddesk_chat_total Total chat questions")
    lines.append("# TYPE golddesk_chat_total counter")
    lines.append(f"golddesk_chat_total {chat_total}")

    lines.append("# HELP golddesk_api_errors_total Total API errors")
    lines.append("# TYPE golddesk_api_errors_total counter")
    lines.append(f"golddesk_api_errors_total {api_errors_total}")

    # Histograms
    for name, values in [
        ("snapshot", _snapshot_durations),
        ("backtest", _backtest_durations),
        ("dca", _dca_durations),
    ]:
        if not values:
            continue
        lines.append(f"# HELP golddesk_{name}_seconds Duration of {name} operation")
        lines.append(f"# TYPE golddesk_{name}_seconds histogram")
        for p in [0.5, 0.9, 0.95, 0.99]:
            lines.append(f'golddesk_{name}_seconds{{quantile="{p}"}} {_percentile(values, p):.6f}')
        lines.append(f"golddesk_{name}_seconds_sum {sum(values):.2f}")
        lines.append(f"golddesk_{name}_seconds_count {len(values)}")

    # WS clients
    lines.append("# HELP golddesk_ws_clients Active WebSocket clients")
    lines.append("# TYPE golddesk_ws_clients gauge")
    lines.append(f"golddesk_ws_clients {ws_client_count()}")

    return "\n".join(lines) + "\n"
