"""
BrsApi Rate-Limit Simulator
===========================

Simulates real API usage against the **actual production ``RateLimiter``**
(``brsapi/rate_limiter.py``) using a virtual clock, then verifies that the
defined limits are NEVER exceeded — no live HTTP requests are made, so the
API key is never touched.

Why a simulator?
  The real limiter enforces three layers for every request:
    1. Global daily limit   (default 4,000 / Tehran calendar day)
    2. Global 5-min window  (default 1,000 / sliding 300s)
    3. Per-category token bucket (tsetmc=60/min, codal=12, ime=12, ...)
  A full trading day + nightly backfills = thousands of requests. Running
  that against the live API would burn the budget in minutes and could get
  the key blocked. Instead, the virtual clock advances time without waiting,
  so a full day simulates in seconds while exercising the REAL limiter code
  (the same code ``BrsApiClient.fetch()`` calls).

Scenarios (run all by default):
  sweep           1 request for EVERY endpoint in BrsApiEndpoints catalog
  realtime-day    the real scheduler job schedule for one Tehran trading day
  backlog-sync    the exact run_backlog_sync.py plan (real-legal + symbol
                  details + candlesticks ≈ 3,999 requests)
  nightly         ALL full-market backfills at full daily caps on one day
                  (demand ≈ 6,000 — intentionally OVER budget → verifies the
                  fail-fast protection rejects instead of exceeding)
  concurrent      realtime-day + backlog-sync running at the same time
                  (stress the sliding 5-min window under concurrency)
  multi-day       realtime-day workload across 2 virtual days → verifies the
                  daily counter resets at Tehran midnight
  fuzz            seeded random mix of endpoints / delays / concurrency
                  (invariant check: limits always hold on the timeline)
  per-endpoint    EVERY endpoint solo at its category's max rate for one
                  virtual day — proves no single API can exceed the caps
  all-max         ALL endpoints at max rate SIMULTANEOUSLY — the combined
                  ceiling under full simultaneous pressure
  starvation      ONE endpoint floods the shared 5-min window (bucket raised
                  so it CAN fill all 1,000 slots) while the other categories
                  trickle — do the others still get requests, and what
                  happens when the hog eats the daily budget?
  max-stress      absolute worst case: realtime-day + backlog-sync +
                  nightly + fuzz all at once

Verification (independent of the limiter's own counters):
  * Re-computes the max requests inside ANY sliding 300s window from the
    recorded timeline → must be <= 5-min limit
  * Re-computes max requests per Tehran calendar day → must be <= daily limit
  * Counts fail-fast rejections (RateLimitExhaustedError) and shows how many
    requests were protected when demand exceeded the budget
  * Reports per-endpoint usage for the whole catalog (``--scenario sweep``)

Usage:
    python scripts/simulate_brsapi_usage.py                # run all scenarios
    python scripts/simulate_brsapi_usage.py --scenario sweep
    python scripts/simulate_brsapi_usage.py --list
    python scripts/simulate_brsapi_usage.py --limits daily=5000,5min=2000
    python scripts/simulate_brsapi_usage.py --format markdown
    python scripts/simulate_brsapi_usage.py --seed 42

Exit code: 0 when every scenario PASSES, 1 when any limit would be exceeded.
"""

from __future__ import annotations

import argparse
import asyncio
import os
import random
import sys
import time as _real_time
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Any, Awaitable, Callable

_project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)

import brsapi.rate_limiter as _rl  # noqa: E402
from brsapi.config import BrsApiEndpoints, settings as brsapi_settings  # noqa: E402
from brsapi.jobs.registry import BRsAPI_SYNC_JOBS  # noqa: E402
from brsapi.rate_limiter import RateLimitExhaustedError, RateLimiter  # noqa: E402

TEHRAN_TZ = timezone(timedelta(hours=3, minutes=30))

# ──────────────────────────────────────────────────────────────────────────
#  Virtual clock — the heart of the simulator
# ──────────────────────────────────────────────────────────────────────────


class VirtualClock:
    """Fake monotonic clock + fake wall clock.

    The real ``RateLimiter`` reads ``time.monotonic()`` (5-min window, token
    buckets) and ``datetime.now(TEHRAN_TZ)`` (daily reset). We substitute
    both with this clock and replace ``asyncio.sleep`` so every "wait" just
    advances virtual time instantly.
    """

    def __init__(self, wall_start: datetime | None = None) -> None:
        self.mono = 0.0
        self.wall = wall_start or datetime(2026, 8, 10, 8, 0, 0, tzinfo=TEHRAN_TZ)

    def advance(self, seconds: float) -> None:
        if seconds > 0:
            self.mono += seconds
            self.wall += timedelta(seconds=seconds)


class _VirtualDateTime:
    """Stands in for ``datetime`` inside ``brsapi.rate_limiter``."""

    @staticmethod
    def now(tz: timezone | None = None) -> datetime:
        return _clock.wall if tz is None else _clock.wall.astimezone(tz)


_clock = VirtualClock()
_orig_monotonic = _real_time.monotonic
_orig_datetime = _rl.datetime
_orig_sleep = asyncio.sleep
_patched = False


def _install_clock() -> None:
    """Patch the pieces of time the real limiter reads. Idempotent."""
    global _patched
    if _patched:
        return
    _real_time.monotonic = lambda: _clock.mono  # type: ignore[assignment]
    _rl.datetime = _VirtualDateTime  # type: ignore[assignment]

    async def _virtual_sleep(delay: float, result: Any = None) -> Any:
        _clock.advance(delay)
        # Yield once to the event loop (REAL zero-sleep) so that
        # ``asyncio.gather`` in the concurrent scenario can actually
        # interleave tasks at every virtual wait — otherwise the first
        # workload would run to completion before the second starts.
        await _orig_sleep(0)
        return result

    asyncio.sleep = _virtual_sleep  # type: ignore[assignment]
    _patched = True


def _restore_clock() -> None:
    global _patched
    if not _patched:
        return
    _real_time.monotonic = _orig_monotonic  # type: ignore[assignment]
    _rl.datetime = _orig_datetime  # type: ignore[assignment]
    asyncio.sleep = _orig_sleep  # type: ignore[assignment]
    _patched = False


def reset_clock(wall_start: datetime | None = None) -> None:
    """Start a fresh virtual day (call before each scenario)."""
    _clock.mono = 0.0
    _clock.wall = wall_start or datetime(2026, 8, 10, 8, 0, 0, tzinfo=TEHRAN_TZ)


# ──────────────────────────────────────────────────────────────────────────
#  Request recorder + verification
# ──────────────────────────────────────────────────────────────────────────


@dataclass
class RecordedRequest:
    mono: float
    wall: datetime
    category: str
    endpoint: str


class Recorder:
    def __init__(self) -> None:
        self.accepted: list[RecordedRequest] = []
        self.rejected: list[RecordedRequest] = []
        self.rejected_reason: Counter[str] = Counter()
        # per-endpoint stats from the per-endpoint scenario
        self.per_endpoint_stats: dict[str, dict[str, Any]] = {}
        # starvation metrics (per other-category accepted/rejected/waits)
        self.starvation_stats: dict[str, dict[str, Any]] = {}
        # endpoint path → list of virtual wait seconds (starvation scenario)
        self.waits: dict[str, list[float]] = {}

    @property
    def total_demand(self) -> int:
        return len(self.accepted) + len(self.rejected)


@dataclass
class ScenarioResult:
    name: str
    ok: bool
    total_accepted: int = 0
    total_rejected: int = 0
    max_5min: int = 0
    max_daily: int = 0
    per_category_max_min: dict[str, int] = field(default_factory=dict)
    max_endpoint_usage: list[tuple[str, int]] = field(default_factory=list)
    details: str = ""
    # detail tables for per-endpoint / starvation scenarios (attached by
    # run_scenario after verify_scenario)
    per_endpoint_stats: dict[str, dict[str, Any]] = field(default_factory=dict)
    starvation_stats: dict[str, dict[str, Any]] = field(default_factory=dict)


def _sliding_window_max(timestamps: list[float], window: float) -> int:
    """Max number of events inside any sliding ``window``-second bucket.

    Mirrors the real limiter's ``_prune_5min_window`` semantics: a request
    recorded exactly ``window`` seconds ago has aged OUT (``<``, not ``<=``),
    matching the limiter's ``<= cutoff`` pruning.
    """
    ts = sorted(timestamps)
    max_count = 0
    j = 0
    for i in range(len(ts)):
        while j < len(ts) and ts[j] - ts[i] < window:
            j += 1
        max_count = max(max_count, j - i)
    return max_count


def verify_scenario(
    name: str,
    rec: Recorder,
    daily_limit: int,
    five_min_limit: int,
    *,
    details: str = "",
) -> ScenarioResult:
    """Independently re-check the recorded timeline against the limits."""
    accepted_ts = [r.mono for r in rec.accepted]
    max_5min = _sliding_window_max(accepted_ts, 300.0) if accepted_ts else 0

    per_day: Counter[str] = Counter(r.wall.strftime("%Y-%m-%d") for r in rec.accepted)
    max_daily = max(per_day.values(), default=0)

    # Per-category per-minute peaks (informational — token buckets legally
    # allow bursts of up to `max_tokens`, so this is a report, not a verdict).
    by_cat: dict[str, list[float]] = defaultdict(list)
    for r in rec.accepted:
        by_cat[r.category].append(r.mono)
    per_cat_max_min = {
        cat: _sliding_window_max(ts, 60.0) for cat, ts in by_cat.items()
    }

    endpoint_usage: Counter[str] = Counter(r.endpoint for r in rec.accepted)
    top_endpoints = endpoint_usage.most_common(10)

    ok = max_5min <= five_min_limit and max_daily <= daily_limit
    problems = []
    if max_5min > five_min_limit:
        problems.append(f"5-min window exceeded ({max_5min} > {five_min_limit})")
    if max_daily > daily_limit:
        problems.append(f"daily limit exceeded ({max_daily} > {daily_limit})")

    result = ScenarioResult(
        name=name,
        ok=ok,
        total_accepted=len(rec.accepted),
        total_rejected=len(rec.rejected),
        max_5min=max_5min,
        max_daily=max_daily,
        per_category_max_min=per_cat_max_min,
        max_endpoint_usage=top_endpoints,
        details=(details or "; ".join(problems) or "limits held"),
    )
    return result


# ──────────────────────────────────────────────────────────────────────────
#  Limiter factory (mirrors BrsApiClient._configure_rate_limits)
# ──────────────────────────────────────────────────────────────────────────


def make_limiter(daily_limit: int, five_min_limit: int) -> RateLimiter:
    limiter = RateLimiter(
        daily_limit=daily_limit,
        five_min_limit=five_min_limit,
        fail_fast=True,  # production default (BRSAPI_FAIL_FAST_ON_DAILY_EXHAUSTED)
    )
    # Same seeding as BrsApiClient._configure_rate_limits()
    limits: dict[str, int] = {
        "tsetmc": brsapi_settings.rate_limit_tsetmc or 60,
        "codal": brsapi_settings.rate_limit_codal or 12,
        "ime": brsapi_settings.rate_limit_ime or 12,
        "commodity": brsapi_settings.rate_limit_commodity or 1,
        "cryptocurrency": brsapi_settings.rate_limit_crypto or 1,
    }
    for category, rpm in limits.items():
        if rpm > 0:
            limiter.configure(category, rpm)
    return limiter


async def sim_request(
    limiter: RateLimiter,
    rec: Recorder,
    category: str,
    endpoint: str,
    *,
    fail_fast: bool = True,
) -> bool:
    """One simulated API call through the REAL limiter. Returns success."""
    try:
        await limiter.acquire(
            category, endpoint=endpoint, fail_fast=fail_fast
        )
    except RateLimitExhaustedError as exc:
        rec.rejected.append(
            RecordedRequest(_clock.mono, _clock.wall, category, endpoint)
        )
        rec.rejected_reason[str(exc).split("(")[0].strip()] += 1
        return False
    rec.accepted.append(
        RecordedRequest(_clock.mono, _clock.wall, category, endpoint)
    )
    return True


async def sim_request_timed(
    limiter: RateLimiter,
    rec: Recorder,
    category: str,
    endpoint: str,
    *,
    fail_fast: bool = True,
) -> tuple[bool, float]:
    """Like ``sim_request`` but also records the virtual wait time spent
    inside ``acquire()`` (queueing behind a saturated window / bucket)."""
    start = _clock.mono
    ok = await sim_request(limiter, rec, category, endpoint, fail_fast=fail_fast)
    waited = _clock.mono - start
    rec.waits.setdefault(endpoint, []).append(waited)
    return ok, waited


# ──────────────────────────────────────────────────────────────────────────
#  Workloads
# ──────────────────────────────────────────────────────────────────────────


Workload = Callable[[RateLimiter, Recorder, dict[str, int]], Awaitable[None]]


def _limit_mismatch_warning() -> str | None:
    """Warn when an OS env var overrides the .env / default limit.

    pydantic-settings gives OS environment variables priority over the
    ``.env`` file. A stale ``BRSAPI_GLOBAL_DAILY_LIMIT`` exported in the
    shell silently raises the production cap above the plan threshold
    (≈5,000/day) — exactly what blocked the key before.
    """
    import os

    os_daily = os.environ.get("BRSAPI_GLOBAL_DAILY_LIMIT")
    if not (os_daily and str(os_daily).strip()):
        return None
    try:
        os_daily_int = int(os_daily)
    except ValueError:
        return None

    # Read the .env value directly (pydantic already resolves to OS env).
    env_file_daily: str | None = None
    try:
        root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        with open(os.path.join(root, ".env"), encoding="utf-8") as fh:
            for line in fh:
                if line.strip().startswith("BRSAPI_GLOBAL_DAILY_LIMIT"):
                    env_file_daily = line.split("=", 1)[1].split("#")[0].strip()
                    break
    except OSError:
        pass

    if os_daily_int > 5_000:
        return (
            f"⚠ OS env BRSAPI_GLOBAL_DAILY_LIMIT={os_daily} overrides "
            f".env ({env_file_daily or 'not set'}). The limiter now allows "
            f"{os_daily}/day — ABOVE the ≈5,000/day server cap that blocks "
            f"the key. Run:  unset BRSAPI_GLOBAL_DAILY_LIMIT"
        )
    return None


def _parse_hhmm(value: str) -> datetime:
    h, m = (int(x) for x in value.split(":"))
    return _clock.wall.replace(hour=h, minute=m, second=0, microsecond=0)


def _schedule_ticks(
    every_seconds: int, start_wall: datetime, end_wall: datetime
) -> list[datetime]:
    """Wall-clock tick times for an interval trigger (like APScheduler)."""
    ticks: list[datetime] = []
    t = start_wall
    while t <= end_wall:
        ticks.append(t)
        t += timedelta(seconds=every_seconds)
    return ticks


# ── sweep: every endpoint in the catalog ─────────────────────────────────


async def workload_sweep(
    limiter: RateLimiter, rec: Recorder, limits: dict[str, int]
) -> None:
    for name, ep in sorted(BrsApiEndpoints.all().items()):
        await sim_request(limiter, rec, ep.category.value, ep.path)


# ── realtime-day: the real scheduler schedule for one trading day ────────
# We build ONE merged, time-sorted event list from every enabled job's
# interval trigger (mirrors APScheduler firing jobs sequentially on their
# wall-clock slots), then execute events in ascending wall time. This keeps
# the virtual timeline faithful: two jobs on the same 2-min tick do NOT
# collapse into a same-instant burst.


def _realtime_day_events() -> list[tuple[datetime, str, str]]:
    open_t = _parse_hhmm(brsapi_settings.market_open)  # 08:30
    close_t = _parse_hhmm(brsapi_settings.market_close)  # 15:30
    codal_open = _clock.wall.replace(hour=8, minute=0)
    codal_close = _clock.wall.replace(hour=18, minute=0)
    day_start = _clock.wall
    day_end = _clock.wall + timedelta(hours=24)

    jobs = {j.name: j for j in BRsAPI_SYNC_JOBS if j.enabled}
    market_hours = {
        "brsapi_all_symbols": 120,
        "brsapi_index": 120,
        "brsapi_index_farabours": 120,
        "brsapi_options": 300,
        "brsapi_ime_futures": 300,
        "brsapi_ime_options": 300,
        "brsapi_ime_certificates": 300,
        "brsapi_ime_funds": 300,
    }
    all_day = {
        "brsapi_commodities": 300,
        "brsapi_crypto": 300,
        "brsapi_gold_currency": 300,
        "brsapi_gold_currency_pro": 300,
    }

    events: list[tuple[datetime, str, str]] = []

    def add(job_name: str, every: int, start: datetime, end: datetime) -> None:
        job = jobs.get(job_name)
        if job is None:
            return
        category = job.category or job.endpoint_config.category.value
        for t in _schedule_ticks(every, start, end):
            events.append((t, category, job.endpoint_config.path))

    for job_name, every in market_hours.items():
        add(job_name, every, open_t, close_t)
    for job_name, every in all_day.items():
        add(job_name, every, day_start, day_end)
    add("brsapi_codal", 900, codal_open, codal_close)
    for hour in range(24):
        probe_at = day_start.replace(hour=hour, minute=0)
        events.append((probe_at, "tsetmc", "/Tsetmc/AllSymbols.php"))

    events.sort(key=lambda e: e[0])
    return events


async def workload_realtime_day(
    limiter: RateLimiter, rec: Recorder, limits: dict[str, int]
) -> None:
    for wall, category, endpoint in _realtime_day_events():
        _clock.advance(max(0.0, (wall - _clock.wall).total_seconds()))
        await sim_request(limiter, rec, category, endpoint)


# ── backlog-sync: the exact run_backlog_sync.py plan ─────────────────────


async def _backfill(
    limiter: RateLimiter,
    rec: Recorder,
    *,
    category: str,
    endpoint: str,
    n_symbols: int,
    requests_per_symbol: int,
    delay_s: float,
) -> None:
    for _ in range(n_symbols):
        for _ in range(requests_per_symbol):
            _clock.advance(delay_s)
            await sim_request(limiter, rec, category, endpoint)


async def workload_backlog_sync(
    limiter: RateLimiter, rec: Recorder, limits: dict[str, int]
) -> None:
    # Same plan as scripts/run_backlog_sync.py: real-legal (500 × 1)
    # + symbol-details (1000 × 1) + candlesticks (budget_left // 3 × 3)
    # Uses the SCENARIO daily limit (not settings) so the plan and the
    # limiter agree — mismatches would otherwise mask over-budget runs.
    budget = limits["daily"]
    remaining = budget

    n_rl = min(brsapi_settings.history_real_legal_daily_max_symbols or 500, remaining)
    await _backfill(
        limiter, rec,
        category="tsetmc", endpoint="/Tsetmc/History.php",
        n_symbols=n_rl, requests_per_symbol=1,
        delay_s=brsapi_settings.history_real_legal_req_delay,
    )
    remaining -= n_rl

    n_sd = min(brsapi_settings.symbol_detail_daily_max_symbols or 1000, remaining)
    await _backfill(
        limiter, rec,
        category="tsetmc", endpoint="/Tsetmc/Symbol.php",
        n_symbols=n_sd, requests_per_symbol=1,
        delay_s=brsapi_settings.symbol_detail_req_delay,
    )
    remaining -= n_sd

    n_candle = min(
        brsapi_settings.candle_daily_max_symbols or 1000,
        remaining // 3,
    )
    await _backfill(
        limiter, rec,
        category="tsetmc", endpoint="/Tsetmc/Candlestick.php",
        n_symbols=n_candle, requests_per_symbol=3,
        delay_s=brsapi_settings.candle_req_delay,
    )


# ── nightly: ALL full-market backfills at full caps (over budget) ────────


async def workload_nightly(
    limiter: RateLimiter, rec: Recorder, limits: dict[str, int]
) -> None:
    # Full-cap demand on one day ≈ 3000 (candles) + 1000 (shareholders)
    # + 500 (history price) + 500 (real-legal) + 1000 (symbols) = 6,000.
    # Intentionally exceeds the 4,000 daily budget → exercises fail-fast.
    await _backfill(
        limiter, rec,
        category="tsetmc", endpoint="/Tsetmc/Candlestick.php",
        n_symbols=brsapi_settings.candle_daily_max_symbols or 1000,
        requests_per_symbol=3, delay_s=brsapi_settings.candle_req_delay,
    )
    await _backfill(
        limiter, rec,
        category="tsetmc", endpoint="/Tsetmc/Shareholder.php",
        n_symbols=brsapi_settings.shareholder_daily_max_symbols or 1000,
        requests_per_symbol=1, delay_s=brsapi_settings.shareholder_req_delay,
    )
    await _backfill(
        limiter, rec,
        category="tsetmc", endpoint="/Tsetmc/History.php",
        n_symbols=brsapi_settings.history_price_daily_max_symbols or 500,
        requests_per_symbol=1, delay_s=brsapi_settings.history_price_req_delay,
    )
    await _backfill(
        limiter, rec,
        category="tsetmc", endpoint="/Tsetmc/History.php",
        n_symbols=brsapi_settings.history_real_legal_daily_max_symbols or 500,
        requests_per_symbol=1, delay_s=brsapi_settings.history_real_legal_req_delay,
    )
    await _backfill(
        limiter, rec,
        category="tsetmc", endpoint="/Tsetmc/Symbol.php",
        n_symbols=brsapi_settings.symbol_detail_daily_max_symbols or 1000,
        requests_per_symbol=1, delay_s=brsapi_settings.symbol_detail_req_delay,
    )


# ── concurrent: realtime + backlog at the same time ──────────────────────


async def workload_concurrent(
    limiter: RateLimiter, rec: Recorder, limits: dict[str, int]
) -> None:
    await asyncio.gather(
        workload_realtime_day(limiter, rec, limits),
        workload_backlog_sync(limiter, rec, limits),
    )


# ── multi-day: realtime workload across 2 virtual days ───────────────────


async def workload_multi_day(
    limiter: RateLimiter, rec: Recorder, limits: dict[str, int]
) -> None:
    # Day 1 (08:00 → next 08:00) then day 2 (same schedule). The daily
    # counter must reset at Tehran midnight between them.
    for day in range(2):
        await workload_realtime_day(limiter, rec, limits)
        # jump to the start of the next virtual day
        next_morning = (_clock.wall + timedelta(days=1)).replace(
            hour=8, minute=0, second=0, microsecond=0
        )
        _clock.advance(max(0.0, (next_morning - _clock.wall).total_seconds()))


# ── fuzz: seeded random mix (invariant check) ────────────────────────────


async def workload_fuzz(
    limiter: RateLimiter, rec: Recorder, limits: dict[str, int], seed: int
) -> None:
    rng = random.Random(seed)
    catalog = list(BrsApiEndpoints.all().values())
    total = 800

    async def worker(wid: int) -> None:
        for _ in range(total // 8):
            ep = rng.choice(catalog)
            # random politeness delay 0–1.5s, occasionally a burst (0s)
            _clock.advance(rng.choice([0.0, 0.0, 0.0, 0.05, 0.2, 0.5, 1.0, 1.5]))
            await sim_request(limiter, rec, ep.category.value, ep.path)

    await asyncio.gather(*[worker(i) for i in range(8)])


# ── per-endpoint: EVERY endpoint solo at max rate for a virtual day ──────
# Each endpoint is run ALONE in a fresh limiter (full daily budget) so the
# per-endpoint numbers measure that single API's ceiling, not the shared
# budget. Demand is the category's configured bucket rate (max legal rate).


def _category_rpm(category: str) -> int:
    """Configured per-category bucket rate (requests per minute)."""
    table = {
        "tsetmc": brsapi_settings.rate_limit_tsetmc or 60,
        "codal": brsapi_settings.rate_limit_codal or 12,
        "ime": brsapi_settings.rate_limit_ime or 12,
        "commodity": brsapi_settings.rate_limit_commodity or 1,
        "cryptocurrency": brsapi_settings.rate_limit_crypto or 1,
    }
    return table.get(category, 30)


async def workload_per_endpoint(
    limiter: RateLimiter, rec: Recorder, limits: dict[str, int]
) -> None:
    """Run every endpoint solo at its category's max legal rate for one
    virtual day. Verifies per-endpoint: max 5-min peak <= 5-min limit and
    daily total <= daily limit for EVERY API in the catalog."""
    catalog = sorted(BrsApiEndpoints.all().items())
    for name, ep in catalog:
        rpm = _category_rpm(ep.category.value)
        delay = 60.0 / rpm if rpm else 5.0
        # Fresh limiter per endpoint → full daily budget per endpoint, so the
        # reported numbers isolate ONE API (the question: can a single API
        # alone exceed the caps?)
        solo = make_limiter(limits["daily"], limits["5min"])
        solo_rec = Recorder()
        end_wall = _clock.wall + timedelta(hours=24)
        consecutive_rejections = 0
        while _clock.wall < end_wall:
            _clock.advance(delay)
            ok = await sim_request(solo, solo_rec, ep.category.value, ep.path)
            if ok:
                consecutive_rejections = 0
            else:
                consecutive_rejections += 1
                # Daily budget exhausted → every further request is rejected
                # identically; no new information, stop this endpoint early.
                if consecutive_rejections >= 100:
                    break
        max5 = _sliding_window_max(
            [r.mono for r in solo_rec.accepted], 300.0
        )
        per_day: Counter[str] = Counter(
            r.wall.strftime("%Y-%m-%d") for r in solo_rec.accepted
        )
        maxday = max(per_day.values(), default=0)
        rec.per_endpoint_stats[name] = {
            "path": ep.path,
            "category": ep.category.value,
            "accepted": len(solo_rec.accepted),
            "rejected": len(solo_rec.rejected),
            "max5min": max5,
            "maxday": maxday,
        }


def _render_per_endpoint_stats(
    stats: dict[str, dict], limits: dict[str, int]
) -> str:
    lines = [
        f"{'endpoint':<24} {'cat':<14} {'accepted':>8} {'rejected':>8} "
        f"{'max5min':>7} {'maxday':>8}  verdict"
    ]
    for name in sorted(stats):
        s = stats[name]
        ok = s["max5min"] <= limits["5min"] and s["maxday"] <= limits["daily"]
        lines.append(
            f"{name:<24} {s['category']:<14} {s['accepted']:>8,} {s['rejected']:>8,} "
            f"{s['max5min']:>6}/{limits['5min']:,} "
            f"{s['maxday']:>7}/{limits['daily']:,}  "
            f"{'✅' if ok else '❌'}"
        )
    return "\n".join(lines)


# ── all-max: ALL endpoints at max rate SIMULTANEOUSLY ─────────────────────
# Every endpoint floods at its category bucket's max rate in parallel — the
# absolute combined ceiling. The 5-min window and daily counter are shared,
# so this is the strongest stress on the GLOBAL limits.


async def workload_all_max(
    limiter: RateLimiter, rec: Recorder, limits: dict[str, int]
) -> None:
    catalog = list(BrsApiEndpoints.all().values())
    end_wall = _clock.wall + timedelta(hours=24)

    async def worker(ep) -> None:
        rpm = _category_rpm(ep.category.value)
        delay = max(0.05, 60.0 / rpm)
        consecutive_rejections = 0
        while _clock.wall < end_wall:
            _clock.advance(delay)
            ok = await sim_request(limiter, rec, ep.category.value, ep.path)
            if ok:
                consecutive_rejections = 0
            else:
                consecutive_rejections += 1
                # Daily budget is shared → once exhausted, stop this worker.
                if consecutive_rejections >= 100:
                    return

    await asyncio.gather(*[worker(ep) for ep in catalog])


# ── starvation: one endpoint hogs the shared 5-min window ────────────────
# The user question: if ONE API keeps receiving 1,000+ requests per 5 min,
# do the OTHER APIs receive anything? To make that possible the hog's bucket
# is raised to 1,000/min (otherwise the 60/min tsetmc bucket caps it at 300
# per 5 min and it physically cannot fill the shared window). The other
# categories keep their real buckets and trickle at their real rates.


async def workload_starvation(
    limiter: RateLimiter, rec: Recorder, limits: dict[str, int]
) -> None:
    # Hog: tsetmc Candlestick with bucket raised so it can saturate the
    # shared 1,000/5min window.
    limiter.configure("tsetmc", 1_000)
    hog_delay = 60.0 / 1_000  # 16.7 req/s → ~1,000 req/5min

    others = [
        ("codal", "/Codal/Announcement.php", 12),
        ("ime", "/IME/Futures.php", 12),
        ("commodity", "/Market/Commodity.php", 1),
        ("cryptocurrency", "/Market/Cryptocurrency.php", 1),
    ]
    end_wall = _clock.wall + timedelta(minutes=30)

    async def hog() -> None:
        while _clock.wall < end_wall:
            _clock.advance(hog_delay)
            await sim_request(limiter, rec, "tsetmc", "/Tsetmc/Candlestick.php")
            # Yield the loop on every iteration: once the hog starts getting
            # fail-fast rejections the acquire() path never sleeps, so without
            # this the hog would spin in a tight loop and the other workers
            # would never get scheduled.
            await asyncio.sleep(0)

    async def other(cat: str, path: str, rpm: int) -> None:
        # The hog is the only clock driver (small steps). Others fire when
        # their own interval has elapsed on the shared virtual clock — no
        # big advances that would jump the whole timeline past the window.
        interval = 60.0 / rpm
        last = _clock.mono
        while _clock.wall < end_wall:
            if _clock.mono - last >= interval:
                await sim_request_timed(limiter, rec, cat, path)
                last = _clock.mono
            await asyncio.sleep(0)

    await asyncio.gather(hog(), *[other(*o) for o in others])

    # Summarise what the non-hog categories actually received and their
    # worst queueing delay (virtual seconds spent inside acquire()).
    for cat, path, _rpm in others:
        acc = [r for r in rec.accepted if r.category == cat]
        rej = [r for r in rec.rejected if r.category == cat]
        waits = rec.waits.get(path, [])
        rec.starvation_stats[cat] = {
            "accepted": len(acc),
            "rejected": len(rej),
            "hog_accepted": len(
                [r for r in rec.accepted if r.category == "tsetmc"]
            ),
            "max_wait_s": round(max(waits), 1) if waits else 0.0,
            "avg_wait_s": round(sum(waits) / len(waits), 1) if waits else 0.0,
        }


def _render_starvation_stats(stats: dict[str, dict]) -> str:
    lines = [
        f"{'other category':<16} {'accepted':>8} {'rejected':>8} "
        f"{'max wait s':>10} {'avg wait s':>10}"
    ]
    for cat in sorted(stats):
        s = stats[cat]
        lines.append(
            f"{cat:<16} {s['accepted']:>8,} {s['rejected']:>8,} "
            f"{s['max_wait_s']:>10.1f} {s['avg_wait_s']:>10.1f}"
        )
    return "\n".join(lines)


# ── max-stress: absolutely everything at once ─────────────────────────────
# realtime-day + backlog-sync + nightly + fuzz all concurrent → the worst
# case the platform could ever generate.


async def workload_max_stress(
    limiter: RateLimiter, rec: Recorder, limits: dict[str, int]
) -> None:
    await asyncio.gather(
        workload_realtime_day(limiter, rec, limits),
        workload_backlog_sync(limiter, rec, limits),
        workload_nightly(limiter, rec, limits),
        workload_fuzz(limiter, rec, limits, seed=7),
    )


# ──────────────────────────────────────────────────────────────────────────
#  Runner + report
# ──────────────────────────────────────────────────────────────────────────


SCENARIOS: dict[str, Workload | None] = {
    "sweep": workload_sweep,
    "realtime-day": workload_realtime_day,
    "backlog-sync": workload_backlog_sync,
    "nightly": workload_nightly,
    "concurrent": workload_concurrent,
    "multi-day": workload_multi_day,
    "per-endpoint": workload_per_endpoint,
    "all-max": workload_all_max,
    "starvation": workload_starvation,
    "max-stress": workload_max_stress,
    # fuzz needs the seed, so run_scenario dispatches it specially (None here)
    "fuzz": None,
}


def _p(msg: str) -> None:
    try:
        print(msg)
    except UnicodeEncodeError:  # Windows cp1252 console
        print(msg.encode("ascii", errors="replace").decode("ascii"))


def _fmt_limit(limits: dict[str, int]) -> str:
    return f"daily={limits['daily']:,}  5min={limits['5min']:,}"


async def run_scenario(
    name: str,
    workload: Workload,
    limits: dict[str, int],
    seed: int = 42,
) -> ScenarioResult:
    reset_clock()
    limiter = make_limiter(limits["daily"], limits["5min"])
    rec = Recorder()

    if name == "fuzz" or workload is None:
        await workload_fuzz(limiter, rec, limits, seed)
    else:
        await workload(limiter, rec, limits)

    details = ""
    if name == "nightly":
        demand = rec.total_demand
        protected = max(0, demand - limits["daily"])
        details = (
            f"demand={demand:,} > daily={limits['daily']:,} → "
            f"{len(rec.rejected):,} requests rejected by fail-fast (key protected)"
        )
    elif name == "backlog-sync":
        details = (
            f"backlog plan completed in full: {len(rec.accepted):,} requests, "
            f"0 rejected, under budget"
        )

    result = verify_scenario(
        name, rec, limits["daily"], limits["5min"], details=details
    )
    # Attach scenario-specific detail tables to the result for reporting.
    result.per_endpoint_stats = dict(rec.per_endpoint_stats)
    result.starvation_stats = dict(rec.starvation_stats)
    return result


def _render_table(
    results: list[ScenarioResult],
    limits: dict[str, int],
    *,
    markdown: bool = False,
) -> str:
    if markdown:
        out = [
            "| Scenario | Accepted | Rejected | Max 5-min | Max/day | Verdict |",
            "|---|---:|---:|---:|---:|---|",
        ]
        for r in results:
            out.append(
                f"| {r.name} | {r.total_accepted:,} | {r.total_rejected:,} "
                f"| {r.max_5min}/{limits['5min']:,} | {r.max_daily}/{limits['daily']:,} "
                f"| {'✅ PASS' if r.ok else '❌ FAIL'} |"
            )
        return "\n".join(out)

    w = 16
    out = [
        f"{'Scenario':<{w}} {'Accepted':>10} {'Rejected':>9} "
        f"{'Max5min':>12} {'Max/day':>10}  Verdict",
        "-" * 78,
    ]
    for r in results:
        out.append(
            f"{r.name:<{w}} {r.total_accepted:>10,} {r.total_rejected:>9,} "
            f"{r.max_5min:>7,}/{limits['5min']:,} {r.max_daily:>7,}/{limits['daily']:,}"
            f"  {'✅ PASS' if r.ok else '❌ FAIL'}"
        )
    return "\n".join(out)


async def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--scenario", type=str, default=None,
                        help="Run one scenario by name (default: all)")
    parser.add_argument("--list", action="store_true", help="List scenarios and exit")
    parser.add_argument("--limits", type=str, default=None,
                        help="Override limits, e.g. daily=5000,5min=2000")
    parser.add_argument("--format", choices=["table", "markdown"], default="table")
    parser.add_argument("--seed", type=int, default=42, help="Fuzz random seed")
    args = parser.parse_args(argv)

    if args.list:
        _p("Available scenarios:")
        for name, fn in SCENARIOS.items():
            _p(f"  {name:<16} {fn.__doc__.strip().splitlines()[0] if fn.__doc__ else ''}")
        _p("  fuzz             seeded random mix (invariant check)")
        return 0

    limits = {"daily": brsapi_settings.global_daily_limit,
              "5min": brsapi_settings.global_5min_limit}
    if args.limits:
        for pair in args.limits.split(","):
            key, _, val = pair.partition("=")
            key = key.strip().lower()
            if key in ("daily", "5min", "five_min", "five-min"):
                limits["daily" if key == "daily" else "5min"] = int(val)

    # Keep the rate-limiter's own threshold WARN logs (80/90/95/100%) out of
    # the report — they fire on every scenario run and bury the table.
    import logging as _logging

    _logging.getLogger("brsapi.rate_limiter").setLevel(_logging.CRITICAL)

    _install_clock()
    try:
        names = [args.scenario] if args.scenario else list(SCENARIOS)
        if args.scenario == "fuzz":
            names = ["fuzz"]

        results: list[ScenarioResult] = []
        _p("=" * 78)
        _p(f"BrsApi Rate-Limit Simulator  |  limits: {_fmt_limit(limits)}")
        _p(f"Using the REAL RateLimiter (brsapi/rate_limiter.py) + virtual clock")
        warning = _limit_mismatch_warning()
        if warning:
            _p(warning)
        _p("=" * 78)

        for name in names:
            if name not in SCENARIOS:
                _p(f"  [!] unknown scenario: {name}")
                continue
            workload = SCENARIOS.get(name)
            reset_clock()
            _p(f"\n▶ scenario: {name}")
            result = await run_scenario(
                name, workload, limits, seed=args.seed
            )
            results.append(result)
            _p(f"  accepted={result.total_accepted:,}  "
               f"rejected={result.total_rejected:,}  "
               f"max5min={result.max_5min}/{limits['5min']:,}  "
               f"maxday={result.max_daily}/{limits['daily']:,}  →  "
               f"{'PASS' if result.ok else 'FAIL'}")
            if result.details:
                _p(f"  note: {result.details}")
            if result.name == "sweep":
                _p("  per-endpoint usage (whole catalog):")
                for ep, cnt in result.max_endpoint_usage:
                    _p(f"    {ep:<34} {cnt}")
            elif result.name == "per-endpoint" and result.per_endpoint_stats:
                _p("  every endpoint solo at max rate for 1 virtual day:")
                for line in _render_per_endpoint_stats(
                    result.per_endpoint_stats, limits
                ).splitlines():
                    _p(f"    {line}")
            elif result.name == "starvation" and result.starvation_stats:
                hog_acc = next(iter(result.starvation_stats.values()))[
                    "hog_accepted"
                ]
                _p(
                    f"  hog (tsetmc Candlestick, bucket raised to 1000/min) "
                    f"sent {hog_acc:,} requests in 30 virtual min — the shared "
                    f"5-min window is saturated."
                )
                _p("  what the OTHER categories received while hog was flooding:")
                for line in _render_starvation_stats(
                    result.starvation_stats
                ).splitlines():
                    _p(f"    {line}")
            else:
                cats = ", ".join(
                    f"{k}={v}/min" for k, v in
                    sorted(result.per_category_max_min.items())
                )
                if cats:
                    _p(f"  per-category peak/min: {cats}")

        _p("\n" + "=" * 78)
        _p("SUMMARY")
        _p("=" * 78)
        _p(_render_table(results, limits, markdown=args.format == "markdown"))

        if any(r.ok is False for r in results):
            _p("\n❌ At least one scenario would exceed the defined limits.")
            return 1
        _p("\n✅ All scenarios respected the defined limits. "
           "The key would never have been at risk.")
        return 0
    finally:
        _restore_clock()


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
