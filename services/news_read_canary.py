"""Canary rollout of the ``news_items`` read path (trap-safe migration).

Implements the strategy documented in ``docs/RUNBOOK_NEWS_READ_CANARY.md``:

* **Mode dial** — ``off`` → ``shadow`` → ``canary`` → ``full``, per
  worker, driven by ``NEWS_READ_MODE`` (+ the legacy boolean forcing
  ``full``). ``off`` and ``full`` behave exactly like the previous
  single boolean — this module is purely additive to the old flag.
* **Shadow probe** — in every non-``full`` mode the served (legacy)
  result is *also* computed on ``news_items`` and compared: parity =
  same page of articles by natural key (URL/title — ids are NOT
  comparable across schemas) + same total. Counts go to Redis (INCR +
  window TTL) so all workers aggregate into one decision-ready window.
* **Canary slice** — in ``canary`` mode a deterministic hash of a
  request discriminator (item id / query / symbol + paging) decides
  which requests are served from ``news_items``; the rest stay legacy
  and are still shadow-probed.
* **Auto-halt** — the halter job flips the mode back to ``off`` (Redis
  flag, read by every worker) when parity over the window drops below
  ``news_read_parity_floor_percent`` with at least
  ``news_read_parity_min_samples`` compared requests. Manual restart
  clears the halt key; flip-back is data-safe because writes always go
  to both schemas.

Redis is optional: without it the module degrades to in-memory counters
(single worker) and shadow results still compare — rollout just loses
cross-worker aggregation.
"""

from __future__ import annotations

import hashlib
import time
from typing import Any

from core.cache import get_cache
from core.config import settings
from core.logging import get_logger
from core.result import PaginatedResult

logger = get_logger(__name__)

# Redis key namespace (all TTL-windowed).
_PREFIX = "news:read_path"
_HALT_KEY = f"{_PREFIX}:halt"
_MODE_KEY = f"{_PREFIX}:mode"
_WINDOW_TTL = 3600  # rolling hour

MODES = ("off", "shadow", "canary", "full")


def normalize_mode(raw: str | None) -> str:
    mode = (raw or "").strip().lower()
    return mode if mode in MODES else "off"


# ── mode resolution (per request, cheap) ─────────────────────────────────


class ReadPathDecision:
    """Which repo serves the request + whether to shadow-probe it."""

    __slots__ = ("serve_items", "serve_legacy", "shadow")

    def __init__(self, serve_items: bool, serve_legacy: bool, shadow: bool) -> None:
        self.serve_items = serve_items      # route to NewsItemsReadRepo
        self.serve_legacy = serve_legacy    # route to legacy _NewsDbRepo
        self.shadow = shadow                # additionally probe the other path

    @property
    def mode(self) -> str:
        if self.serve_items and not self.serve_legacy:
            return "full" if not self.shadow else "canary"
        return "shadow" if self.shadow else "off"


async def resolve_mode() -> str:
    """Effective mode for this request.

    Precedence: Redis halt flag → legacy boolean (full) → Redis mode
    (cross-worker runtime dial) → settings.news_read_mode. The Redis
    keys let operators flip/halt all workers without a rollout; the
    settings value remains the per-deploy default.
    """
    if getattr(settings, "news_read_from_items", False):
        return "full"
    cache = get_cache()
    if not cache.is_connected or cache.client is None:
        return normalize_mode(getattr(settings, "news_read_mode", "off"))
    try:
        if await cache.client.get(_HALT_KEY):
            return "off"
        runtime = await cache.client.get(_MODE_KEY)
        if runtime:
            return normalize_mode(runtime if isinstance(runtime, str) else runtime.decode())
    except Exception:  # noqa: BLE001 — dial must never break reads
        logger.debug("news read-mode dial unavailable", exc_info=True)
    return normalize_mode(getattr(settings, "news_read_mode", "off"))


def _canary_bucket(discriminator: str, percent: int) -> bool:
    """Stable per-request bucket: same discriminator always lands on the
    same side, so a client retry does not flicker between schemas."""
    if percent >= 100:
        return True
    if percent <= 0:
        return False
    digest = hashlib.sha256(discriminator.encode("utf-8", "replace")).digest()
    return (digest[0] << 8 | digest[1]) < percent * 65535 // 100


def decide(mode: str, discriminator: str) -> ReadPathDecision:
    """Pure routing decision for one read request in ``mode``."""
    if mode == "full":
        return ReadPathDecision(serve_items=True, serve_legacy=False, shadow=False)
    if mode == "canary":
        in_slice = _canary_bucket(discriminator, settings.news_read_canary_percent)
        if in_slice:
            return ReadPathDecision(serve_items=True, serve_legacy=False, shadow=False)
        return ReadPathDecision(serve_items=False, serve_legacy=True, shadow=True)
    if mode == "shadow":
        return ReadPathDecision(serve_items=False, serve_legacy=True, shadow=True)
    return ReadPathDecision(serve_items=False, serve_legacy=True, shadow=False)


# ── parity counters (Redis window, in-memory fallback) ───────────────────


_mem_counters: dict[str, int] = {}


async def _incr(name: str, n: int = 1) -> None:
    cache = get_cache()
    if cache.is_connected and cache.client is not None:
        try:
            key = f"{_PREFIX}:{name}"
            await cache.client.incrby(key, n)
            await cache.client.expire(key, _WINDOW_TTL)
            return
        except Exception:  # noqa: BLE001 — counters are best-effort
            logger.debug("read-path counter incr failed", exc_info=True)
    _mem_counters[name] = _mem_counters.get(name, 0) + n


async def record(
    decision: ReadPathDecision,
    *,
    compared: bool,
    parity: bool,
    divergence_kind: str = "true_divergence",
) -> None:
    """Record one served request. ``compared``/``parity`` only apply to
    shadow probes (and canary-shadow leftovers).

    ``divergence_kind`` splits divergences for the halter:
    * ``true_divergence`` — items serve LESS than legacy (or different
      rows): a read-path regression, counts toward auto-halt.
    * ``items_superset`` — items serve MORE (alias/spelling-variant
      resolution the legacy LIKE-match lacks): a deliberate improvement,
      tracked separately and NOT counted toward auto-halt.
    """
    await _incr("served")
    if decision.serve_items:
        await _incr("served_items")
    if not compared:
        return
    await _incr("compared")
    if parity:
        await _incr("parity_ok")
    else:
        await _incr("parity_divergent")
        await _incr(f"divergence_{divergence_kind}")
        if divergence_kind == "true_divergence":
            logger.warning(
                "news read-path parity divergence — legacy vs news_items page differs"
            )
        else:
            logger.debug(
                "news read-path items-superset divergence (deliberate alias coverage)"
            )


async def window_stats() -> dict[str, Any]:
    """Snapshot of the current window for the status endpoint / halter."""
    cache = get_cache()
    stats: dict[str, Any] = {
        "served": 0, "served_items": 0, "compared": 0,
        "parity_ok": 0, "parity_divergent": 0,
        "http_total": 0, "http_5xx": 0,
    }
    if cache.is_connected and cache.client is not None:
        try:
            pipe_values = await cache.client.mget(
                [f"{_PREFIX}:{k}" for k in stats]
            )
            for key, raw in zip(stats, pipe_values):
                stats[key] = int(raw) if raw else 0
        except Exception:  # noqa: BLE001
            logger.debug("read-path stats read failed", exc_info=True)
            stats |= _mem_counters
    else:
        stats |= _mem_counters

    compared = stats["compared"]
    ok = stats["parity_ok"]
    stats["parity_percent"] = round(ok * 100.0 / compared, 2) if compared else None
    # Regression-only parity: charges true divergences (regressions)
    # against the floor; deliberate items-superset divergences (alias
    # coverage) are excluded — they serve MORE, never less.
    true_div = stats.get("divergence_true_divergence", 0)
    regressions = ok + true_div
    stats["regression_parity_percent"] = (
        round(ok * 100.0 / regressions, 2) if regressions else (None if compared else 100.0)
    )
    stats["items_share_percent"] = (
        round(stats["served_items"] * 100.0 / stats["served"], 2) if stats["served"] else 0.0
    )
    stats["http_5xx_percent"] = (
        round(stats["http_5xx"] * 100.0 / stats["http_total"], 2) if stats["http_total"] else 0.0
    )
    stats["window"] = _WINDOW_TTL
    return stats


async def compare_page(
    legacy: PaginatedResult[Any] | None, items: PaginatedResult[Any] | None
) -> bool:
    """Parity = same total and same *natural-key* ordering on the page.

    Ids CANNOT be compared across schemas by design: legacy ids are
    ``news_<24hex>`` (core.ids.new_id) while ``news_items.id`` is a
    generated BIGINT surfaced as ``ni_<n>`` — tails never match, so any
    id-based check would be permanently divergent and trip auto-halt.
    The stable cross-schema key is the article URL (mirrored verbatim by
    the dual-write), with title as fallback for url-less rows.
    """
    if legacy is None or items is None:
        return False
    if legacy.total != items.total:
        return False
    if len(legacy.items) != len(items.items):
        return False

    def _key(x: Any) -> str:
        url = str(getattr(x, "url", "") or "")
        if url.strip():
            return url
        return str(getattr(x, "title", "") or "")

    return all(_key(a) == _key(b) for a, b in zip(legacy.items, items.items))


# ── auto-halt (halter job calls this) ────────────────────────────────────


# ── HTTP error-rate counters (same window, same TTL) ─────────────────

# Counted from the MetricsMiddleware: every /news request bumps the total;
# every >=500 response bumps the 5xx counter. This is the second leg of
# the auto-halt — parity divergence cannot see infrastructure failures
# because a failed request never produces a page to compare (real case:
# 2026-09-20 shadow window, 8-min Postgres OOM burst → 338 HTTP 500s,
# invisible to parity, invisible to the halter).


async def record_http_outcome(path: str, status_code: int) -> None:
    """Count one finished /news request (total + 5xx) into the window.

    Called from ``MetricsMiddleware`` for ``/api/v1/news`` paths — best-
    effort, never raises, so monitoring can never break serving.
    """
    # Exact prefix with boundary — /api/v1/newsarchive must NOT match.
    if not (path == "/api/v1/news" or path.startswith("/api/v1/news/")):
        return
    try:
        await _incr("http_total")
        if status_code >= 500:
            await _incr("http_5xx")
    except Exception:  # noqa: BLE001 — counters are best-effort
        logger.debug("read-path http counter failed", exc_info=True)


async def evaluate_auto_halt() -> dict[str, Any]:
    """Check the window against the parity floor; flip the shared mode to
    ``off`` when breached. Returns a decision summary for the job result.

    The parity metric charged against the floor EXCLUDES
    ``items_superset`` divergences: those are the new read path finding
    MORE than legacy (spelling-variant + tag-alias resolution the legacy
    LIKE-match lacks) — a deliberate improvement, not a regression.
    """
    stats = await window_stats()
    compared = stats["compared"]
    floor = settings.news_read_parity_floor_percent
    min_samples = settings.news_read_parity_min_samples
    http_total = int(stats.get("http_total", 0))
    http_5xx = int(stats.get("http_5xx", 0))
    http_5xx_percent = round(http_5xx * 100.0 / http_total, 2) if http_total else 0.0
    result: dict[str, Any] = {
        "checked": True,
        "compared": compared,
        "parity_percent": stats["parity_percent"],
        "regression_parity_percent": stats.get("regression_parity_percent"),
        "floor": floor,
        "http_total": http_total,
        "http_5xx": http_5xx,
        "http_5xx_percent": http_5xx_percent,
        "halted": False,
        "reason": None,
    }
    if not settings.news_read_halt_enabled:
        result["reason"] = "halt disabled"
        return result
    parity = stats.get("regression_parity_percent")
    if compared < min_samples:
        # Not enough parity evidence — but the HTTP tripwire below is
        # still evaluated: a 5xx burst hits exactly when parity samples
        # are scarce (failed requests never reach parity accounting).
        result["reason"] = f"not enough samples ({compared} < {min_samples})"
    elif parity is not None and parity < floor:
        await _trip_halt(parity, floor, compared, mode_reason="parity")
        if await resolve_mode() == "off":
            result["halted"] = True
            result["reason"] = f"parity {parity}% below floor {floor}%"
    else:
        result["reason"] = "parity within floor"
    # Second leg — HTTP error-rate tripwire. INDEPENDENT of the parity
    # sample gate: a burst of 5xx can hit while compared counts are still
    # low (failed requests never reach parity accounting), so it uses its
    # own min-total threshold.
    if (
        not result["halted"]
        and settings.news_read_http_error_halt_enabled
        and http_total >= settings.news_read_http_error_min_total
        and http_5xx_percent >= settings.news_read_http_error_max_percent
    ):
        await _trip_halt(http_5xx_percent, settings.news_read_http_error_max_percent, http_total, mode_reason="http_errors")
        if await resolve_mode() == "off":
            result["halted"] = True
            result["reason"] = (
                f"http 5xx rate {http_5xx_percent}% >= {settings.news_read_http_error_max_percent}% "
                f"({http_5xx}/{http_total})"
            )
    return result


async def _trip_halt(
    observed: float, threshold: float, samples: int, *, mode_reason: str
) -> None:
    """Set the shared halt flag (best-effort — mirrors the original
    inline halt block; never raises)."""
    cache = get_cache()
    mode_before = await resolve_mode()
    if mode_before == "off":
        return
    if cache.is_connected and cache.client is not None:
        await cache.client.set(_HALT_KEY, "1")
        await cache.client.delete(_MODE_KEY)
    else:
        settings.news_read_mode = "off"
    logger.error(
        "news read-path AUTO-HALT (%s): %.2f%% breached threshold %.2f%% over %d samples "
        "(mode %s → off). Flip back by clearing %s after the issue is fixed.",
        mode_reason, observed, threshold, samples, mode_before, _HALT_KEY,
    )


async def set_runtime_mode(mode: str) -> None:
    """Operator dial (all workers, no deploy): writes the shared Redis key.
    Also clears any halt when moving to a non-off mode."""
    mode = normalize_mode(mode)
    cache = get_cache()
    if cache.is_connected and cache.client is not None:
        if mode == "off":
            await cache.client.delete(_MODE_KEY)
        else:
            await cache.client.set(_MODE_KEY, mode)
            await cache.client.delete(_HALT_KEY)
    else:
        settings.news_read_mode = mode


async def halt_status() -> dict[str, Any]:
    cache = get_cache()
    halted = False
    if cache.is_connected and cache.client is not None:
        try:
            halted = bool(await cache.client.get(_HALT_KEY))
        except Exception:  # noqa: BLE001
            halted = False
    return {"halted": halted, "mode": await resolve_mode(), **await window_stats()}


def now_monotonic() -> float:
    """Exposed for tests (timing not part of the decision logic)."""
    return time.monotonic()
