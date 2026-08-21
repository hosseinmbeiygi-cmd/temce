"""
BrsApi Usage Recorder
=====================

The **reporting** side of the BrsApi budget system.

The :class:`~brsapi.budget.BrsApiBudgetGovernor` enforces the daily/5-min caps
with *persistent* counters (Redis / file) so the key never gets blocked again.
This recorder is what makes that usage **visible**: it aggregates granted
requests and HTTP 302 blocks per Tehran day in memory, then flushes them to
``brsapi_daily_usage`` in PostgreSQL so the admin panel can render a
historical daily-usage report (``GET /api/v1/brsapi/manage/usage``).

Why a table and not just the governor's live counters?
-------------------------------------------------------
- The governor's Redis/file counter only holds *today*.  The admin panel also
  wants last week / last month — which needs a persistent history.
- Redis is a cache (key can be evicted, TTL expires at Tehran midnight);
  PostgreSQL is the durable source of truth for reporting.

Design
------
- **Batched writes:** request counts accumulate in memory and are flushed on a
  background timer (default every 60s) or on demand — no DB round-trip per
  request.
- **Additive, cross-process safe:** the flush is an ``INSERT ... ON CONFLICT
  (usage_date) DO UPDATE SET request_count = request_count + EXCLUDED...`` so
  every API worker adds its own counters to the shared daily row instead of
  overwriting it.
- **Resilient:** if the DB is down the counters stay in memory and the next
  flush retries; nothing is lost unless the process dies mid-window.

Wiring
------
- ``brsapi/budget.py`` calls ``record_used()`` after a granted request and
  ``record_block()`` on an HTTP 302.
- ``apps/api/app.py`` starts the background flusher at startup and flushes on
  shutdown.
"""

from __future__ import annotations

import asyncio
import contextlib
from datetime import datetime, timedelta, timezone
from logging import getLogger
from typing import Any

logger = getLogger(__name__)

TEHRAN_TZ = timezone(timedelta(hours=3, minutes=30))
DEFAULT_FLUSH_INTERVAL = 60.0  # seconds between background flushes

# Retry the DB after this delay if the factory was missing (app still booting).
_RETRY_FACTORY_DELAY = 15.0


def tehran_today() -> str:
    """Tehran calendar date as ``YYYY-MM-DD`` (same key the governor uses)."""
    return datetime.now(TEHRAN_TZ).strftime("%Y-%m-%d")


class BrsApiUsageRecorder:
    """In-memory per-day usage aggregator flushed to ``brsapi_daily_usage``.

    Usage::

        from brsapi.usage_recorder import get_usage_recorder

        recorder = get_usage_recorder()
        recorder.record_used(tokens=1)          # hot path — no I/O
        recorder.record_block(location)         # HTTP 302 observed
        await recorder.flush()                  # manual flush (or background timer)
    """

    def __init__(
        self,
        flush_interval: float = DEFAULT_FLUSH_INTERVAL,
        session_factory: Any | None = None,
    ) -> None:
        self._flush_interval = flush_interval
        self._factory = session_factory  # async_sessionmaker or async callable
        # day -> {"count": int, "blocked": int, "blocked_at": dt|None,
        #         "last_request_at": dt|None}
        self._days: dict[str, dict[str, Any]] = {}
        self._task: asyncio.Task | None = None
        self._enabled = True

    # ── Hot-path recording (sync, no I/O) ─────────────────────────

    def record_used(self, tokens: int = 1) -> None:
        """Count one granted live request for today."""
        if not self._enabled or tokens <= 0:
            return
        entry = self._days.setdefault(tehran_today(), self._new_entry())
        entry["count"] += tokens
        entry["last_request_at"] = datetime.now(TEHRAN_TZ)

    def record_block(self, location: str = "") -> None:
        """Count one HTTP 302 over-quota block for today."""
        if not self._enabled:
            return
        entry = self._days.setdefault(tehran_today(), self._new_entry())
        entry["blocked"] += 1
        entry["blocked_at"] = datetime.now(TEHRAN_TZ)
        logger.warning("BrsApi usage recorder: 302 block recorded (%r)", location)

    def disable(self) -> None:
        """Stop recording (used by tests / kill-switch). Idempotent."""
        self._enabled = False

    def pending_days(self) -> dict[str, dict[str, Any]]:
        """Snapshot of days still waiting to be flushed (for tests/monitoring)."""
        return {k: dict(v) for k, v in self._days.items()}

    @staticmethod
    def _new_entry() -> dict[str, Any]:
        return {"count": 0, "blocked": 0, "blocked_at": None, "last_request_at": None}

    # ── Flush ─────────────────────────────────────────────────────

    async def flush(self) -> dict[str, Any]:
        """Flush in-memory aggregates to ``brsapi_daily_usage``.

        Uses an additive ``ON CONFLICT (usage_date) DO UPDATE`` upsert so
        multiple workers can run concurrently. Counters are only cleared from
        memory after a successful commit — a failed flush keeps them for the
        next attempt.

        Returns a small report ``{"flushed_days": int, "error": str|None}``.
        Never raises.
        """
        if not self._days:
            return {"flushed_days": 0, "error": None}
        days = dict(self._days)
        try:
            from sqlalchemy.dialects.postgresql import insert

            from brsapi.models.base import BrsApiDailyUsageModel

            factory = self._factory
            if factory is None:
                from core.database import async_session_factory
                factory = async_session_factory
            if factory is None:
                return {"flushed_days": 0, "error": "db factory unavailable"}

            daily_limit = self._current_daily_limit()

            async with factory() as session:
                for day, agg in days.items():
                    stmt = insert(BrsApiDailyUsageModel).values(
                        usage_date=day,
                        request_count=agg["count"],
                        daily_limit=daily_limit,
                        blocked_count=agg["blocked"],
                        blocked_at=agg["blocked_at"],
                        last_request_at=agg["last_request_at"],
                    )
                    stmt = stmt.on_conflict_do_update(
                        index_elements=[BrsApiDailyUsageModel.usage_date],
                        set_={
                            # Additive — each process/instance adds its share.
                            "request_count": BrsApiDailyUsageModel.request_count
                            + stmt.excluded.request_count,
                            "blocked_count": BrsApiDailyUsageModel.blocked_count
                            + stmt.excluded.blocked_count,
                            # Keep the newest timestamp of the two.
                            "blocked_at": _greatest_ts(
                                BrsApiDailyUsageModel.blocked_at, stmt.excluded.blocked_at
                            ),
                            "last_request_at": _greatest_ts(
                                BrsApiDailyUsageModel.last_request_at,
                                stmt.excluded.last_request_at,
                            ),
                            "daily_limit": _coalesce(
                                stmt.excluded.daily_limit, BrsApiDailyUsageModel.daily_limit
                            ),
                            "updated_at": func_now(),
                        },
                    )
                    await session.execute(stmt)
                await session.commit()

            # Only forget the day after a successful commit.
            for day in days:
                self._days.pop(day, None)
            return {"flushed_days": len(days), "error": None}
        except Exception as exc:  # noqa: BLE001 — recorder must never crash callers
            logger.debug("BrsApi usage flush failed (%s) — counters kept in memory", exc)
            return {"flushed_days": 0, "error": str(exc)}

    def _current_daily_limit(self) -> int | None:
        """Snapshot of the configured daily cap, when available."""
        try:
            from brsapi.rate_limiter import get_rate_limiter
            return int(get_rate_limiter()._daily_limit or 0) or None
        except Exception:  # noqa: BLE001
            return None

    # ── Background flusher ────────────────────────────────────────

    def start(self) -> None:
        """Start the periodic background flusher (idempotent)."""
        if self._task is not None and not self._task.done():
            return
        self._task = asyncio.create_task(self._run_flusher())

    async def stop(self) -> None:
        """Stop the flusher and flush whatever is still pending."""
        task, self._task = self._task, None
        if task is not None and not task.done():
            task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await task
        await self.flush()

    async def _run_flusher(self) -> None:
        while True:
            await asyncio.sleep(self._flush_interval)
            try:
                await self.flush()
            except Exception:  # noqa: BLE001
                logger.exception("BrsApi usage flusher error")


# ── SQL helper expressions (kept tiny so the flush loop reads clearly) ──────


def _greatest_ts(a: Any, b: Any) -> Any:
    from sqlalchemy import func
    return func.greatest(a, b)


def _coalesce(a: Any, b: Any) -> Any:
    from sqlalchemy import func
    return func.coalesce(a, b)


def func_now() -> Any:
    from sqlalchemy import func
    return func.now()


# ── Global singleton ──────────────────────────────────────────────


_recorder: BrsApiUsageRecorder | None = None


def get_usage_recorder() -> BrsApiUsageRecorder:
    """Return the process-wide usage recorder (attached to the budget
    governor singleton)."""
    global _recorder
    if _recorder is None:
        _recorder = BrsApiUsageRecorder()
    return _recorder
