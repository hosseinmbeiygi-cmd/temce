"""
Armor Job State — api/job_state.py
====================================
Shared precompute job state machine for the Armor Dashboard.

The precompute Celery workers publish the 4 contract events
(contracts/events.md) through api/ws_manager.ArmorWsManager:

    PRECOMPUTATION_PROGRESS
    PRECOMPUTATION_GROUP_COMPLETED
    PRECOMPUTATION_COMPLETED
    SYMBOL_RESULT_UPDATED

This module consumes those events and maintains the live job status that
GET /api/precompute/status and GET /api/dashboard/ready serve.  The state is
persisted to Redis (Hot layer) so it is visible across processes; an
in-memory fallback keeps dev/test runs working without Redis.

Event handlers update with *absolute* counters from the event payloads (never
deltas), which makes handling idempotent — safe against the double delivery
that happens when the same process both publishes to Redis and subscribes to
its own channel.

Decoupling: imports only core.cache — never from ingestion / precompute /
frontend.
"""
from __future__ import annotations

import time
from datetime import UTC, datetime
from typing import Any

from core.cache import get_cache
from core.logging import get_logger

logger = get_logger(__name__)

REDIS_STATUS_KEY = "armor:precompute:status"

# Group advance order (contracts/events.md group semantics: A -> B -> C)
_GROUP_ORDER: dict[str, str | None] = {"A": "B", "B": "C", "C": None}

# In-memory fallback state (dev / test / Redis-down). Mirrors what is stored
# in Redis so both paths serve the same shape.
_mem_status: dict[str, Any] | None = None
_started_at: float | None = None

# Per-symbol result fallback (fed by SYMBOL_RESULT_UPDATED events). Mirrors
# the Redis results hash for dev/test runs without Redis so the summary and
# dashboard-ready endpoints still serve real computed data.
_mem_results: dict[str, dict[str, Any]] = {}

# Reentrancy guard: _all_done runs while the COMPLETED event itself is being
# broadcast; the guard prevents a second COMPLETED delivery from re-running.
_finalizing = False

# Event types accepted from the worker pipeline (contracts/events.md)
EVENT_PROGRESS = "PRECOMPUTATION_PROGRESS"
EVENT_GROUP_COMPLETED = "PRECOMPUTATION_GROUP_COMPLETED"
EVENT_COMPLETED = "PRECOMPUTATION_COMPLETED"
EVENT_SYMBOL_UPDATED = "SYMBOL_RESULT_UPDATED"

# Derived event emitted by this module on every state change so dashboard
# clients receive the full recomputed snapshot (overall %, ETA, group rollup),
# not just the raw worker payloads.
EVENT_STATUS_SNAPSHOT = "PRECOMPUTATION_STATUS_SNAPSHOT"

# Only these worker event types may enter handle_event via the broadcast
# funnel — derived/snapshot events are excluded so the state machine can
# never feed back into itself.
STATE_EVENT_TYPES = frozenset(
    {EVENT_PROGRESS, EVENT_GROUP_COMPLETED, EVENT_COMPLETED, EVENT_SYMBOL_UPDATED}
)


# ── Public API ─────────────────────────────────────────────────────
async def load_status() -> dict[str, Any]:
    """Return the live job status dict (Redis first, memory fallback)."""
    cache = get_cache()
    if cache.is_connected:
        try:
            raw = await cache.get(REDIS_STATUS_KEY)
            if isinstance(raw, dict) and "overall_status" in raw:
                return raw
        except Exception:
            logger.debug("precompute status load failed", exc_info=True)
    if _mem_status is not None:
        return dict(_mem_status)
    return default_status()


async def save_status(status: dict[str, Any]) -> None:
    """Persist job status to Redis + memory fallback, then push a live
    PRECOMPUTATION_STATUS_SNAPSHOT to every connected dashboard client.

    The broadcast is fire-and-forget from the state machine's perspective:
    failures are logged and never break persistence or event handling.
    """
    global _mem_status
    _mem_status = dict(status)
    cache = get_cache()
    if cache.is_connected:
        try:
            await cache.set(REDIS_STATUS_KEY, status, ttl=3600)
        except Exception:
            logger.debug("precompute status save failed", exc_info=True)

    # Live push to dashboard clients. Lazy import breaks the module cycle
    # (ws_manager imports job_state inside its funnel). The snapshot type is
    # NOT in STATE_EVENT_TYPES, so the funnel drops it — no recursion.
    try:
        from api.ws_manager import get_armor_ws_manager

        await get_armor_ws_manager().broadcast_raw(EVENT_STATUS_SNAPSHOT, dict(status))
    except Exception:
        logger.debug("precompute status snapshot broadcast failed", exc_info=True)


async def reset_job() -> dict[str, Any]:
    """Initialize a fresh RUNNING job state (called by POST /precompute/start)."""
    global _started_at
    status = default_status()
    status["overall_status"] = "RUNNING"
    status["current_group"] = "A"
    status["last_update"] = _now_iso()
    _started_at = time.time()
    await save_status(status)
    return status


def is_job_active(status: dict[str, Any] | None = None) -> bool:
    """True while a job is RUNNING/RETRYING (used by the start debounce)."""
    if status is None:
        status = _mem_status
    if not status:
        return False
    return status.get("overall_status") in ("RUNNING", "RETRYING")


def default_status() -> dict[str, Any]:
    """The canonical empty status shape (matches PrecomputeStatusResponse)."""
    return {
        "overall_status": "PENDING",
        "current_group": None,
        "total_symbols": 0,
        "completed_symbols": 0,
        "failed_symbols": 0,
        "progress_percent": 0.0,
        "current_symbol": None,
        "estimated_remaining_seconds": None,
        "last_update": _now_iso(),
        "groups": {
            "A": {"total": 0, "completed": 0, "failed": 0, "status": "PENDING"},
            "B": {"total": 0, "completed": 0, "failed": 0, "status": "PENDING"},
            "C": {"total": 0, "completed": 0, "failed": 0, "status": "PENDING"},
        },
    }


# ── Event handlers (the state-machine callbacks) ──────────────────
async def handle_event(event_type: str, payload: dict[str, Any]) -> None:
    """Dispatch a contract event onto the state machine.

    Called from ArmorWsManager._broadcast for every event flowing through
    the pipeline, and safe to call directly from tests / other consumers.
    Derived events (EVENT_STATUS_SNAPSHOT) are intentionally ignored so the
    snapshot broadcasts emitted by save_status can never recurse back here.
    """
    if event_type not in STATE_EVENT_TYPES:
        return
    try:
        if event_type == EVENT_PROGRESS:
            await _update_status(payload)
        elif event_type == EVENT_GROUP_COMPLETED:
            await _group_done(payload)
        elif event_type == EVENT_COMPLETED:
            await _all_done(payload)
        elif event_type == EVENT_SYMBOL_UPDATED:
            _record_symbol_result(payload)
    except Exception:
        # State tracking must never break the broadcast pipeline.
        logger.debug("precompute event handling failed for %s", event_type, exc_info=True)


async def _update_status(payload: dict[str, Any]) -> None:
    """PRECOMPUTATION_PROGRESS — bump per-group counters + overall progress."""
    global _started_at
    status = await load_status()
    group = str(payload.get("group") or "")
    meta = status["groups"].get(group)
    if meta is None:
        return

    # Lazy ETA clock: works even if the job was started by another process
    # (e.g. the gateway adapter) that could not call reset_job() locally.
    if _started_at is None and status.get("overall_status") == "RUNNING":
        _started_at = time.time()

    total = int(payload.get("total") or 0)
    completed = int(payload.get("completed") or 0)
    meta["total"] = total
    meta["completed"] = completed
    meta["status"] = "RUNNING"

    status["current_group"] = group
    status["current_symbol"] = payload.get("current_symbol")
    _recompute_overall(status)
    status["last_update"] = _now_iso()
    await save_status(status)


async def _group_done(payload: dict[str, Any]) -> None:
    """PRECOMPUTATION_GROUP_COMPLETED — finalize a group, advance current_group."""
    status = await load_status()
    group = str(payload.get("group") or "")
    meta = status["groups"].get(group)
    if meta is None:
        return

    total_processed = int(payload.get("total_processed") or meta.get("total") or 0)
    failed = int(payload.get("failed") or 0)
    meta["total"] = total_processed
    meta["completed"] = max(0, total_processed - failed)
    meta["failed"] = failed
    meta["status"] = "SUCCESS"

    status["current_group"] = _GROUP_ORDER.get(group)
    _recompute_overall(status)
    status["last_update"] = _now_iso()
    await save_status(status)


async def _all_done(payload: dict[str, Any]) -> None:
    """PRECOMPUTATION_COMPLETED — finalize the whole job."""
    global _finalizing, _started_at
    if _finalizing:
        return  # re-entrancy guard against duplicate COMPLETED deliveries
    _finalizing = True
    try:
        status = await load_status()

        total = int(payload.get("total") or 0)
        success = int(payload.get("success") or 0)
        failed = int(payload.get("failed") or 0)

        # Defensive: a zeroed final event falls back to the per-group counters.
        if total == 0 and success == 0 and failed == 0:
            _recompute_overall(status)
            total = status["total_symbols"]
            success = status["completed_symbols"]
            failed = status["failed_symbols"]

        status["overall_status"] = str(payload.get("overall_status") or "SUCCESS")
        status["current_group"] = None
        status["current_symbol"] = None
        status["total_symbols"] = total
        status["completed_symbols"] = success
        status["failed_symbols"] = failed
        status["progress_percent"] = 100.0 if total else 0.0
        status["estimated_remaining_seconds"] = 0
        status["last_update"] = _now_iso()

        # The final event is authoritative: the pipeline finished normally, so
        # a group still PENDING/RUNNING (e.g. empty group, or its per-group
        # COMPLETED event was lost) must not linger as RUNNING in the UI.
        # Mark it SUCCESS rather than FAILED — the worker declared completion.
        for meta in status["groups"].values():
            if meta["status"] in ("PENDING", "RUNNING"):
                meta["status"] = "SUCCESS"

        await save_status(status)
        _started_at = None
    finally:
        _finalizing = False


# ── Internal helpers ────────────────────────────────────────────────
def _record_symbol_result(payload: dict[str, Any]) -> None:
    """SYMBOL_RESULT_UPDATED — remember the computed result for the no-Redis
    fallback store. Full payloads (with expires_at etc.) overwrite partial
    ones wholesale; partial payloads merge over a stored full result so a
    partial update can never degrade the cached record.
    """
    symbol = payload.get("symbol")
    if not symbol:
        return
    existing = _mem_results.get(symbol)
    if existing and len(payload) < len(existing):
        existing.update(payload)
        return
    _mem_results[symbol] = dict(payload)


def _recompute_overall(status: dict[str, Any]) -> None:
    """Recompute overall counters from per-group counters + ETA."""
    groups = status["groups"]
    status["total_symbols"] = sum(int(m.get("total") or 0) for m in groups.values())
    status["completed_symbols"] = sum(int(m.get("completed") or 0) for m in groups.values())
    status["failed_symbols"] = sum(int(m.get("failed") or 0) for m in groups.values())
    status["progress_percent"] = round(
        (status["completed_symbols"] / max(1, status["total_symbols"])) * 100, 2
    )
    status["estimated_remaining_seconds"] = _estimate_remaining(status)


def _estimate_remaining(status: dict[str, Any]) -> int | None:
    """Naive ETA: elapsed / completed * remaining. None when not computable."""
    if _started_at is None or not status.get("completed_symbols"):
        return None
    elapsed = time.time() - _started_at
    remaining = status.get("total_symbols", 0) - status["completed_symbols"]
    if remaining <= 0:
        return 0
    per_symbol = elapsed / status["completed_symbols"]
    return int(remaining * per_symbol)


def _now_iso() -> str:
    return datetime.now(UTC).isoformat()
