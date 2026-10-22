"""Prometheus metrics برای GoldDesk — endpoint /metrics.

expose counters + histograms برای monitoring:
- snapshot_build_seconds: زمان ساخت snapshot
- signal_total: تعداد signalهای live
- alert_fired_total: alertهای fired
- backtest_seconds: زمان backtest
- chat_total: تعداد پرسش‌های chat
- ws_clients: تعداد subscriberها

وضعیت‌ها با یک ``threading.Lock`` محافظت می‌شوند (قبلاً متغیرهای گلوبال بدون قفل
و ``_percentile`` فقط ایندکس ساده بود، نه کوانتیل واقعی — GS-27).
"""

from __future__ import annotations

import threading
import time
from collections.abc import Iterator
from contextlib import contextmanager

_LOCK = threading.Lock()

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


def incr(name: str, amount: int = 1) -> None:
    """افزایش thread-safe یک شمارنده (نام مطابق متغیر ماجول)."""
    global snapshot_total, signal_total, alert_fired_total, chat_total, api_errors_total
    with _LOCK:
        if name == "snapshot_total":
            snapshot_total += amount
        elif name == "signal_total":
            signal_total += amount
        elif name == "alert_fired_total":
            alert_fired_total += amount
        elif name == "chat_total":
            chat_total += amount
        elif name == "api_errors_total":
            api_errors_total += amount
        else:
            raise KeyError(f"unknown counter: {name}")


def _record(bucket: list[float], duration: float) -> None:
    with _LOCK:
        bucket.append(duration)


@contextmanager
def measure_snapshot() -> Iterator[None]:
    start = time.monotonic()
    try:
        yield
    finally:
        _record(_snapshot_durations, time.monotonic() - start)


@contextmanager
def measure_backtest() -> Iterator[None]:
    start = time.monotonic()
    try:
        yield
    finally:
        _record(_backtest_durations, time.monotonic() - start)


@contextmanager
def measure_dca() -> Iterator[None]:
    start = time.monotonic()
    try:
        yield
    finally:
        _record(_dca_durations, time.monotonic() - start)


# ── WS clients ──────────────────────────────────────────────


def ws_client_count() -> int:
    try:
        from .ws_hub import get_hub

        return get_hub().client_count()
    except Exception:
        return 0


# ── Render ──────────────────────────────────────────────────


def _percentile(values: list[float], p: float) -> float:
    """کوانتیل با درون‌یابی خطی (روش نوع ۷ / numpy default)؛ نه ایندکس ساده."""
    if not values:
        return 0.0
    sorted_v = sorted(values)
    if len(sorted_v) == 1:
        return sorted_v[0]
    rank = p * (len(sorted_v) - 1)
    lo = int(rank)
    hi = min(lo + 1, len(sorted_v) - 1)
    frac = rank - lo
    return sorted_v[lo] + (sorted_v[hi] - sorted_v[lo]) * frac


def render_prometheus() -> str:
    """رندر همه metrics به فرمت Prometheus text."""
    lines: list[str] = []

    with _LOCK:
        counters = {
            "golddesk_snapshots_total": (snapshot_total, "Total snapshots built"),
            "golddesk_signals_total": (signal_total, "Total live signals detected"),
            "golddesk_alerts_fired_total": (alert_fired_total, "Total alert events fired"),
            "golddesk_chat_total": (chat_total, "Total chat questions"),
            "golddesk_api_errors_total": (api_errors_total, "Total API errors"),
        }
        histograms = [
            ("snapshot", list(_snapshot_durations)),
            ("backtest", list(_backtest_durations)),
            ("dca", list(_dca_durations)),
        ]

    for name, (value, help_text) in counters.items():
        lines.append(f"# HELP {name} {help_text}")
        lines.append(f"# TYPE {name} counter")
        lines.append(f"{name} {value}")

    for name, values in histograms:
        if not values:
            continue
        lines.append(f"# HELP golddesk_{name}_seconds Duration of {name} operation")
        lines.append(f"# TYPE golddesk_{name}_seconds histogram")
        for p in [0.5, 0.9, 0.95, 0.99]:
            lines.append(f'golddesk_{name}_seconds{{quantile="{p}"}} {_percentile(values, p):.6f}')
        lines.append(f"golddesk_{name}_seconds_sum {sum(values):.2f}")
        lines.append(f"golddesk_{name}_seconds_count {len(values)}")

    lines.append("# HELP golddesk_ws_clients Active WebSocket clients")
    lines.append("# TYPE golddesk_ws_clients gauge")
    lines.append(f"golddesk_ws_clients {ws_client_count()}")

    return "\n".join(lines) + "\n"
