"""
Armor Precompute Router — api/routers/precompute_router.py
============================================================
4 endpoints required by the spec:

    POST /api/precompute/start          — enqueue Celery grouped tasks (A/B/C)
    GET  /api/precompute/status         — live PrecomputeStatusResponse from Redis (Hot)
    GET  /api/dashboard/ready           — symbols whose computation is ready (progressive)
    GET  /api/symbols/{symbol}/summary  — single symbol from Redis cache, with STALE label

Storage layers:
    Hot  — Redis (cache.get / cache.client)
    Warm — TimescaleDB/Postgres is NOT touched by this router (read-only cache path)
    Cold — Parquet is NOT touched

Decoupling: only imports from contracts/schemas.py and api/ws_manager.py — never from
ingestion / precompute / frontend.

Reuse: core.cache.get_cache(), core.logging, schemas.common.responses.ApiResponse
"""
from __future__ import annotations

import asyncio
import contextlib
import json
import time
from datetime import UTC, datetime
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Path

from apps.api.dependencies import require_roles

from api.job_state import (
    load_status as _load_status,
    reset_job as _reset_job,
    save_status as _save_status,  # noqa: F401 (re-exported by apps.api.endpoints.precompute)
)


def get_symbol_results() -> dict[str, dict[str, Any]]:
    """The shared per-symbol result fallback store (api/job_state).

    Re-read through the module object each call so tests that reset
    ``job_state._mem_results`` (rebinding the module attribute) are observed
    live rather than through a stale direct reference.
    """
    from api import job_state as _js

    return _js._mem_results

from api.ws_manager import get_armor_ws_manager
from contracts.schemas import (
    JobStatus,
    SymbolComputationResult,
)
from core.cache import get_cache
from core.logging import get_logger
from schemas.common.responses import ApiResponse

logger = get_logger(__name__)
router = APIRouter()

# ── Redis keys (must match api/ws_manager.py) ──────────────────
REDIS_RESULTS_HASH = "armor:precompute:results"
REDIS_START_LOCK = "armor:precompute:lock"
LOCK_TTL_SECONDS = 300  # 5 min debounce for start

# In-memory fallback when Redis is not connected (dev / test without Redis)
_mem_lock_until: float = 0.0
_mem_results: dict[str, dict[str, Any]] = {}

# ── Helpers ──────────────────────────────────────────────────────
def _now_iso() -> str:
    return datetime.now(UTC).isoformat()


def _default_status() -> dict[str, Any]:
    from api.job_state import default_status

    return default_status()


def _empty_groups() -> dict[str, dict[str, Any]]:
    """Empty per-group progress dict (plain shape, matches status snapshots)."""
    return {
        "A": {"total": 0, "completed": 0, "failed": 0, "status": JobStatus.PENDING.value},
        "B": {"total": 0, "completed": 0, "failed": 0, "status": JobStatus.PENDING.value},
        "C": {"total": 0, "completed": 0, "failed": 0, "status": JobStatus.PENDING.value},
    }


async def _load_all_results() -> list[dict[str, Any]]:
    """All computed results: Redis Hot layer first, shared in-memory fallback
    (api.job_state, fed by SYMBOL_RESULT_UPDATED events) second.

    Reads BOTH result layouts — the api hash (armor:precompute:results) and
    the precompute scope's per-symbol keys (precompute:result:{symbol}) —
    without assuming which side wrote last.
    """
    cache = get_cache()
    if not cache.is_connected or cache.client is None:
        return list(get_symbol_results().values())
    try:
        out: dict[str, dict[str, Any]] = {}
        # Layout 1: api-side hash
        raw = await cache.client.hgetall(REDIS_RESULTS_HASH)
        for v in raw.values():
            try:
                obj = json.loads(v) if isinstance(v, str) else v
                if isinstance(obj, dict) and "symbol" in obj:
                    out[obj["symbol"]] = obj
            except Exception:
                continue
        # Layout 2: precompute-scope per-symbol keys (scan is O(matched))
        cursor: int | str = 0
        try:
            while True:
                cursor, keys = await cache.client.scan(
                    cursor=int(cursor), match="precompute:result:*", count=200
                )
                for key in keys:
                    v = await cache.client.get(key)
                    if v is None:
                        continue
                    try:
                        obj = json.loads(v) if isinstance(v, str) else v
                        if isinstance(obj, dict) and "symbol" in obj:
                            out.setdefault(obj["symbol"], obj)
                    except Exception:
                        continue
                cursor = int(cursor)
                if cursor == 0:
                    break
        except Exception:
            logger.debug("precompute:result scan failed", exc_info=True)
        if out:
            return list(out.values())
        return list(get_symbol_results().values())
    except Exception:
        logger.debug("load all results failed", exc_info=True)
        return list(get_symbol_results().values())


async def _load_single_result(symbol: str) -> dict[str, Any] | None:
    """One result: the Redis Hot layer first (authoritative FULL record
    written by the precompute worker), then the shared in-memory fallback
    (fed by SYMBOL_RESULT_UPDATED events, which carry only the contract
    event's partial summary).

    Order matters: the event stream seeds memory with a PARTIAL record
    (symbol/group/armor_score/data_dri/is_unreliable) — preferring it would
    degrade the summary endpoint even while the full hot-layer record is
    available.  Memory is only a fallback for the no-Redis case.
    """
    cache = get_cache()
    if cache.is_connected and cache.client is not None:
        try:
            # Layout 1: api-side hash
            raw = await cache.client.hget(REDIS_RESULTS_HASH, symbol)
            # Layout 2: precompute-scope per-symbol key
            if raw is None:
                raw = await cache.client.get(f"precompute:result:{symbol}")
            if raw is not None:
                obj = json.loads(raw) if isinstance(raw, str) else raw
                if isinstance(obj, dict) and "symbol" in obj:
                    return obj
        except Exception:
            logger.debug("load single result failed for %s", symbol, exc_info=True)
    return get_symbol_results().get(symbol)


def _save_result_mem(result: dict[str, Any]) -> None:
    """Helper for tests / precompute workers to seed mem fallback."""
    _mem_results[result["symbol"]] = result


def _is_stale(expires_at: str | None) -> bool:
    if not expires_at:
        return False
    try:
        # Handle both ISO with Z and +00:00
        exp = expires_at.replace("Z", "+00:00")
        dt = datetime.fromisoformat(exp)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=UTC)
        return dt < datetime.now(UTC)
    except Exception:
        return False


# ── 1. POST /api/precompute/start ────────────────────────────────
@router.post(
    "/start",
    summary="شروع پیش‌محاسبه زرهی (کل بازار)",
    dependencies=[Depends(require_roles("admin"))],  # dispatches a full-market Celery run
)
async def start_precompute() -> ApiResponse[dict[str, Any]]:
    """
    Enqueue the grouped Celery pipeline:
        queue_group_a (high liquidity) -> queue_group_b -> queue_group_c

    Idempotent: if a run is already RUNNING/RETRYING within LOCK_TTL, returns 409.
    Otherwise sets status to RUNNING and dispatches.
    """
    global _mem_lock_until
    cache = get_cache()

    # Debounce via Redis lock (fallback to in-memory when Redis unavailable)
    if cache.is_connected and cache.client is not None:
        try:
            locked = await cache.client.set(REDIS_START_LOCK, _now_iso(), nx=True, ex=LOCK_TTL_SECONDS)
            if not locked:
                status = await _load_status()
                if status.get("overall_status") in (JobStatus.RUNNING.value, JobStatus.RETRYING.value):
                    return ApiResponse[dict[str, Any]](
                        success=False,
                        data=status,
                        error={"message": "Precomputation already in progress", "code": "ALREADY_RUNNING"},
                    )
                await cache.client.set(REDIS_START_LOCK, _now_iso(), ex=LOCK_TTL_SECONDS)
        except Exception:
            logger.debug("start lock check failed", exc_info=True)
    else:
        # In-memory lock for dev/test without Redis
        if time.time() < _mem_lock_until:
            status = await _load_status()
            if status.get("overall_status") in (JobStatus.RUNNING.value, JobStatus.RETRYING.value):
                return ApiResponse[dict[str, Any]](
                    success=False,
                    data=status,
                    error={"message": "Precomputation already in progress", "code": "ALREADY_RUNNING"},
                )
        _mem_lock_until = time.time() + LOCK_TTL_SECONDS

    # Initialize the shared job state machine FIRST so that progress events
    # arriving from the workers (possibly synchronously during dispatch, e.g.
    # the no-Celery fallback path) land on a fresh RUNNING state instead of a
    # stale/terminal one.
    raw_status = await _reset_job()

    # Try to dispatch Celery grouped tasks if available (decoupled — optional)
    dispatched = False
    dispatch_info: dict[str, Any] = {}
    try:
        # Optional Celery import — if precompute workers are not installed, we still mark RUNNING
        # so the frontend can show progress via polling (polling will read the same status key).
        from precompute.workers.celery_tasks import (  # type: ignore
            dispatch_armor_pipeline_async,
            load_symbols_from_ingestion,
        )

        # Async-safe path: Celery dispatch when configured, otherwise the
        # A->B->C pipeline runs on this loop and every contract event lands on
        # ws_manager live.  Symbols come from the ingestion hot layer.
        groups = await load_symbols_from_ingestion()
        result = await dispatch_armor_pipeline_async(groups)
        dispatch_info = {"result": str(result) if result else "enqueued"}
        dispatched = True
    except ImportError:
        logger.info("Celery precompute workers not installed — status set to RUNNING without dispatch")
        dispatch_info = {"celery": False, "reason": "precompute.workers.celery_tasks not available"}
    except Exception as exc:
        logger.exception("Celery dispatch failed")
        dispatch_info = {"celery": False, "reason": str(exc)}

    # Re-read after dispatch: the sync fallback pipeline runs inline and its
    # progress + COMPLETED events flow through ws_manager into job_state via
    # fire-and-forget tasks.  Yield a few ticks so those tasks drain before
    # snapshotting the status (no-op for the Celery path, which just returns).
    for _ in range(8):
        await asyncio.sleep(0)
    raw_status = await _load_status()

    # Broadcast start event
    with contextlib.suppress(Exception):
        mgr = get_armor_ws_manager()
        await mgr.broadcast_raw("PRECOMPUTATION_STARTED", {"timestamp": _now_iso(), "dispatched": dispatched})

    return ApiResponse[dict[str, Any]](
        success=True,
        data={"status": raw_status, "dispatch": dispatch_info},
        message="Precomputation started" if dispatched else "Precomputation marked RUNNING (Celery not available)",
    )


# ── 2. GET /api/precompute/status ───────────────────────────────
@router.get("/status", summary="وضعیت زنده پیش‌محاسبه")
async def get_precompute_status() -> ApiResponse[dict[str, Any]]:
    status = await _load_status()
    # Enrich with live connection count for the banner
    with contextlib.suppress(Exception):
        mgr = get_armor_ws_manager()
        status["_ws_connections"] = mgr.connection_count()
    return ApiResponse[dict[str, Any]](success=True, data=status)


# ── 3. GET /api/dashboard/ready ─────────────────────────────────
@router.get("/dashboard/ready", summary="نمادهای آماده داشبورد (Hot cache)")
async def get_dashboard_ready() -> ApiResponse[list[dict[str, Any]]]:
    """
    Returns all SymbolComputationResult that are ready in Redis (Hot layer).
    Frontend progressively renders A, then B, then C — so we return all,
    and the frontend's visibleGroups logic decides what to show.

    If Redis is unavailable, returns an empty list (frontend will keep Polling).
    """
    results = await _load_all_results()
    # Annotate STALE on the fly (do not mutate stored value)
    for r in results:
        try:
            r["_is_stale"] = _is_stale(r.get("expires_at"))
            # Also expose is_stale alias for frontend convenience
            r["is_stale"] = r["_is_stale"]
        except Exception:
            r["_is_stale"] = False
            r["is_stale"] = False

    # Sort by armor_score desc so the most interesting hits appear first
    with contextlib.suppress(Exception):
        results.sort(key=lambda x: float(x.get("armor_score", 0) or 0), reverse=True)

    return ApiResponse[list[dict[str, Any]]](success=True, data=results)


# ── legacy alias: GET /api/dashboard/ready is also exposed as /api/precompute/ready
@router.get("/ready", include_in_schema=False)
async def get_precompute_ready_alias() -> ApiResponse[list[dict[str, Any]]]:
    return await get_dashboard_ready()


# ── 4. GET /api/symbols/{symbol}/summary ────────────────────────
@router.get("/symbols/{symbol}/summary", summary="خلاصه نماد (با برچسب STALE)")
async def get_symbol_summary(
    symbol: str = Path(..., description="نماد، مثلا فملی یا فولاد"),
) -> ApiResponse[dict[str, Any]]:
    """
    Read the per-symbol result from Redis Hot cache.
    - If found and expires_at < now → annotate _is_stale / is_stale and force JobStatus.STALE in the envelope.
    - If not found → 404 with STALE hint (so the frontend can show cached stale data if it has any).
    - Also falls back to a minimal STALE placeholder so the UI never breaks.
    """
    result = await _load_single_result(symbol)

    if result is None:
        # Try alternative key patterns (legacy)
        cache = get_cache()
        if cache.is_connected:
            with contextlib.suppress(Exception):
                alt = await cache.get(f"armor:symbol:{symbol}")
                if isinstance(alt, dict) and "symbol" in alt:
                    result = alt
                elif isinstance(alt, str):
                    result = json.loads(alt)

    if result is None:
        raise HTTPException(
            status_code=404,
            detail={
                "message": f"Symbol {symbol} not found in Hot cache",
                "symbol": symbol,
                "hint": "No computed result yet — precomputation may still be running (group B/C)",
            },
        )

    # STALE detection
    is_stale = _is_stale(result.get("expires_at"))
    # Validate against Pydantic schema (ensures data_dri 0..100 etc.), but tolerate legacy shapes
    try:
        validated = SymbolComputationResult.model_validate(result)
        payload = json.loads(validated.model_dump_json())
        payload["is_stale"] = is_stale
        payload["_is_stale"] = is_stale
        if is_stale:
            payload["_stale_reason"] = f"expires_at {result.get('expires_at')} is in the past"
    except Exception:
        # Fallback: return raw with staleness annotation
        payload = dict(result)
        payload["is_stale"] = is_stale
        payload["_is_stale"] = is_stale

    # Add cache metadata for debugging
    payload["_cache"] = "redis:hot"
    payload["_stale"] = is_stale
    if is_stale:
        # Frontend should render the STALE badge when _stale is true
        payload["_label"] = JobStatus.STALE.value

    return ApiResponse[dict[str, Any]](success=True, data=payload)
