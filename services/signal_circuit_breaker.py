"""Rolling accuracy circuit breaker for the signal pipeline.

When the most-recent N days of daily signal accuracy drop below a
threshold, signal generation is paused. This is the second of the
"quick wins" identified in ``docs/accuracy-investigation-2026-08.md``
and is a defence against model drift, regime change, and data-pipeline
regressions.

The breaker is intentionally minimal: a single async function that
reads the live ``signal_accuracy`` table, applies a decision rule,
and returns a structured result. The caller (the multi-market
signals pipeline) decides what to do with the verdict — typically
"return an empty signals list with a banner" rather than crash.

Why a fresh module and not extending ``signal_accuracy_tracker``?
The tracker writes outcomes; this module reads them and produces
*operational* decisions. Splitting reads from writes keeps the
tracker pure and avoids the breaker being pulled into the hot
path of every outcome write.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine

# Imported at module level so tests can patch the symbol; the cost of
# always importing core.cache is negligible (it only builds a singleton).
from core.cache import get_cache  # noqa: E402
from core.logging import get_logger

logger = get_logger(__name__)


@dataclass(frozen=True)
class BreakerState:
    """A snapshot of the breaker's decision at one point in time.

    ``tripped=True`` means the recent accuracy is below the threshold
    and the caller should pause signal generation. ``reason`` is a
    short, user-facing explanation safe to surface in the UI.
    """

    tripped: bool
    accuracy_pct: float
    sample_size: int
    window_days: int
    threshold_pct: float
    reason: str
    evaluated_at: datetime
    per_market: dict[str, float] = field(default_factory=dict)


def _env_float(name: str, default: float) -> float:
    """Read a float env var. Falls back to ``default`` if missing or invalid.

    Stays strict on the *first* call: invalid values raise so a typo
    is caught early. If the caller has already validated, the default
    is a no-op.
    """
    raw = os.environ.get(name)
    if raw is None or raw.strip() == "":
        return default
    try:
        return float(raw)
    except ValueError as exc:
        raise ValueError(f"env {name} must be a float, got {raw!r}") from exc


def _env_int(name: str, default: int) -> int:
    raw = os.environ.get(name)
    if raw is None or raw.strip() == "":
        return default
    return int(raw)


async def evaluate(
    engine: AsyncEngine,
    *,
    window_days: int | None = None,
    accuracy_threshold_pct: float | None = None,
    min_samples: int | None = None,
) -> BreakerState:
    """Decide whether the signal pipeline should be paused.

    Args:
        engine: an open SQLAlchemy async engine pointed at the live DB.
        window_days: rolling window size in days. Default 3.
        accuracy_threshold_pct: below this accuracy the breaker trips.
            Default 50 (percent).
        min_samples: minimum number of settled signals in the window
            before the breaker is allowed to trip. With too few samples
            the decision is too noisy to act on. Default 20.

    Returns:
        A :class:`BreakerState` describing the current condition. The
        caller checks ``tripped`` and acts accordingly.
    """
    window = window_days or _env_int("SIGNAL_BREAKER_WINDOW_DAYS", 3)
    threshold = accuracy_threshold_pct or _env_float("SIGNAL_BREAKER_THRESHOLD_PCT", 50.0)
    min_n = min_samples or _env_int("SIGNAL_BREAKER_MIN_SAMPLES", 20)

    # The ``outcome_set_at`` column is stored as a naive timestamp
    # (``DateTime(timezone=False)``), so we must compare with a naive
    # cutoff. Strip tzinfo to avoid asyncpg's "offset-naive vs aware" error.
    cutoff = (datetime.now(UTC) - timedelta(days=window)).replace(tzinfo=None)
    query = text(
        """
        WITH windowed AS (
          SELECT market,
                 COUNT(*) AS n,
                 AVG(CASE WHEN direction_correct THEN 1.0 ELSE 0.0 END) AS acc
          FROM signal_accuracy
          WHERE timeframe = 'daily'
            AND outcome_set_at IS NOT NULL
            AND outcome_set_at >= :cutoff
          GROUP BY market
        )
        SELECT market, n, acc FROM windowed
        """
    )

    per_market: dict[str, float] = {}
    total_n = 0
    weighted_acc_sum = 0.0
    async with engine.connect() as conn:
        rows = (await conn.execute(query, {"cutoff": cutoff})).fetchall()

    for market, n, acc in rows:
        n_int = int(n or 0)
        per_market[market] = round(float(acc or 0.0) * 100, 2)
        total_n += n_int
        weighted_acc_sum += float(acc or 0.0) * n_int

    overall_pct = (weighted_acc_sum / total_n * 100.0) if total_n else 0.0

    if total_n < min_n:
        # Not enough data — default to NOT tripping. Better to over-generate
        # in a cold-start than to silently starve the feed.
        return BreakerState(
            tripped=False,
            accuracy_pct=round(overall_pct, 2),
            sample_size=total_n,
            window_days=window,
            threshold_pct=threshold,
            reason=f"insufficient_samples (n={total_n} < {min_n}); breaker not armed",
            evaluated_at=datetime.now(UTC),
            per_market=per_market,
        )

    if overall_pct < threshold:
        worst = min(per_market.items(), key=lambda kv: kv[1], default=("none", 0.0))
        return BreakerState(
            tripped=True,
            accuracy_pct=round(overall_pct, 2),
            sample_size=total_n,
            window_days=window,
            threshold_pct=threshold,
            reason=(
                f"rolling_{window}d_accuracy {overall_pct:.1f}% < {threshold:.1f}%; "
                f"weakest market: {worst[0]} ({worst[1]:.1f}%)"
            ),
            evaluated_at=datetime.now(UTC),
            per_market=per_market,
        )

    return BreakerState(
        tripped=False,
        accuracy_pct=round(overall_pct, 2),
        sample_size=total_n,
        window_days=window,
        threshold_pct=threshold,
        reason=f"healthy (rolling_{window}d={overall_pct:.1f}% >= {threshold:.1f}%)",
        evaluated_at=datetime.now(UTC),
        per_market=per_market,
    )


async def evaluate_default() -> BreakerState:
    """Convenience wrapper that builds an engine from ``DATABASE_URL``.

    Used by the dry-run script and ad-hoc CLI checks. Production code
    should pass a long-lived engine so we don't churn the connection
    pool on every check.
    """
    db = os.environ.get("DATABASE_URL")
    if not db:
        raise RuntimeError("DATABASE_URL not set")
    engine = create_async_engine(db)
    try:
        return await evaluate(engine)
    finally:
        await engine.dispose()


# ── Cached evaluation ──────────────────────────────────────────────
# Production hot-path: the per-request latency budget for the breaker
# is tight (~0.7s scan + JSON round-trip on the live DB). We cache the
# verdict in Redis for a short TTL so 100 concurrent requests in the
# same minute pay the cost once.
#
# Why short TTL (60s default)?
#   - Long enough to absorb burst traffic on the same minute.
#   - Short enough that a regime change is reflected within ~1 minute
#     (good enough for a manual-trading product; if this were HFT
#     we'd use a CDC stream instead).
#
# Cache key is namespaced so other features can share the same Redis
# instance without colliding.

CACHE_KEY_PREFIX = "signal:circuit_breaker:v1"
DEFAULT_CACHE_TTL_SECONDS = 60


def _cache_key(window_days: int, threshold_pct: float, min_samples: int) -> str:
    return f"{CACHE_KEY_PREFIX}:w{window_days}:t{int(threshold_pct)}:m{min_samples}"


def _state_to_dict(state: BreakerState) -> dict[str, Any]:
    return {
        "tripped": state.tripped,
        "accuracy_pct": state.accuracy_pct,
        "sample_size": state.sample_size,
        "window_days": state.window_days,
        "threshold_pct": state.threshold_pct,
        "reason": state.reason,
        "evaluated_at": state.evaluated_at.isoformat(),
        "per_market": state.per_market,
    }


def _dict_to_state(payload: dict[str, Any]) -> BreakerState:
    return BreakerState(
        tripped=bool(payload["tripped"]),
        accuracy_pct=float(payload["accuracy_pct"]),
        sample_size=int(payload["sample_size"]),
        window_days=int(payload["window_days"]),
        threshold_pct=float(payload["threshold_pct"]),
        reason=str(payload["reason"]),
        evaluated_at=datetime.fromisoformat(payload["evaluated_at"]),
        per_market=dict(payload.get("per_market") or {}),
    )


async def evaluate_cached(
    *,
    window_days: int | None = None,
    accuracy_threshold_pct: float | None = None,
    min_samples: int | None = None,
    ttl_seconds: int | None = None,
) -> BreakerState:
    """Evaluate the breaker with a short-lived Redis cache.

    Behaviour:
      1. Compute the *effective* parameters from env / arguments.
      2. Try the cache key. On hit → return the cached state immediately.
      3. On miss, run the live evaluation via :func:`evaluate_default`
         and write the verdict back to Redis with the given TTL.

    Redis is best-effort: if it is unreachable, we fall through to the
    live evaluation and silently skip the cache write. This keeps the
    breaker functional in environments without a Redis service (CI,
    local dev).

    No new connection pool is created here: the caller's ``get_cache()``
    is reused, so the breaker benefits from the same connection reuse
    as the rest of the API.
    """
    window = window_days or _env_int("SIGNAL_BREAKER_WINDOW_DAYS", 3)
    threshold = accuracy_threshold_pct or _env_float("SIGNAL_BREAKER_THRESHOLD_PCT", 50.0)
    min_n = min_samples or _env_int("SIGNAL_BREAKER_MIN_SAMPLES", 20)
    ttl = ttl_seconds or _env_int("SIGNAL_BREAKER_CACHE_TTL_SECONDS", DEFAULT_CACHE_TTL_SECONDS)

    # Local import is no longer needed — get_cache is imported at module
    # level so test code can patch it via
    # ``patch("services.signal_circuit_breaker.get_cache")``.
    cache = get_cache()
    key = _cache_key(window, threshold, min_n)

    if cache.is_connected:
        try:
            cached = await cache.get(key)
            if isinstance(cached, dict):
                return _dict_to_state(cached)
        except Exception:
            logger.debug("circuit-breaker cache read failed; falling through to live eval", exc_info=True)

    state = await evaluate_default()

    if cache.is_connected:
        try:
            await cache.set(key, _state_to_dict(state), ttl=ttl)
        except Exception:
            logger.debug("circuit-breaker cache write failed; continuing", exc_info=True)

    return state


async def invalidate_cache() -> None:
    """Force the next call to recompute.

    Useful for ops (manual override, post-deploy, post-retrain) where
    the cached verdict may be stale and you want it refreshed *now*
    instead of after the TTL expires.
    """
    cache = get_cache()
    if not cache.is_connected:
        return
    # We don't know which parameter combinations are cached, so we use
    # a SCAN-and-delete loop with the common key prefix. SCAN is safe
    # on a live Redis; KEYS would be O(N) blocking.
    try:
        async for key in cache.client.scan_iter(match=f"{CACHE_KEY_PREFIX}:*", count=100):
            await cache.client.delete(key)
    except Exception:
        logger.debug("circuit-breaker cache invalidation failed", exc_info=True)
