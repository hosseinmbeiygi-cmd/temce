"""
Precompute Armor API — apps/api/endpoints/precompute.py
========================================================
Thin adapter that re-exports the real implementation from api/routers/precompute_router.py
so that the spec file api/routers/precompute_router.py stays the Single Source of Truth
and the existing FastAPI app (apps.api.router) can mount it.

Endpoints (as per spec):
    POST /api/precompute/start
    GET  /api/precompute/status
    GET  /api/dashboard/ready
    GET  /api/symbols/{symbol}/summary

This file provides the same logic but split correctly for the gateway's prefix scheme:
  - precompute_router -> mounted at /precompute
  - dashboard_router  -> mounted at /dashboard  (ready)
  - symbols_router    -> mounted at /symbols   (summary)
"""
from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import Any

from fastapi import APIRouter, HTTPException, Path

from api.routers.precompute_router import (
    _is_stale as _api_is_stale,
    _load_all_results,
    _load_single_result,
    _load_status,
    _save_status,
    start_precompute as start_precompute_canonical,
)
from api.ws_manager import get_armor_ws_manager
from contracts.schemas import GroupProgress, JobStatus, PrecomputeStatusResponse, SymbolComputationResult, SymbolGroup
from core.cache import get_cache
from core.logging import get_logger
from schemas.common.responses import ApiResponse

logger = get_logger(__name__)

# ── Router for /precompute/* (start, status) ────────────────────
router = APIRouter(tags=["Armor Precompute"])

REDIS_START_LOCK = "armor:precompute:lock"
LOCK_TTL_SECONDS = 300


def _now_iso() -> str:
    return datetime.now(UTC).isoformat()


def _empty_groups() -> dict[SymbolGroup, GroupProgress]:
    return {
        SymbolGroup.A: GroupProgress(total=0, completed=0, failed=0, status=JobStatus.PENDING),
        SymbolGroup.B: GroupProgress(total=0, completed=0, failed=0, status=JobStatus.PENDING),
        SymbolGroup.C: GroupProgress(total=0, completed=0, failed=0, status=JobStatus.PENDING),
    }


@router.post("/start", summary="شروع پیش‌محاسبه زرهی (کل بازار)")
async def start_precompute() -> ApiResponse[dict[str, Any]]:
    """Delegate to the canonical implementation in api/routers/precompute_router.py
    (Single Source of Truth).  The canonical handler owns the start debounce,
    job-state reset, and Celery dispatch — duplicating them here caused the
    status snapshot to be overwritten with a fresh RUNNING state after the
    sync-fallback pipeline had already completed."""
    return await start_precompute_canonical()


async def _start_precompute_impl_legacy() -> ApiResponse[dict[str, Any]]:
    cache = get_cache()
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
            logger.debug("precompute start lock check failed", exc_info=True)
    else:
        # In-memory fallback — rely on api/routers mem store lock (already handled there)
        # but also debounce via status check here
        status = await _load_status()
        if status.get("overall_status") in (JobStatus.RUNNING.value, JobStatus.RETRYING.value):
            # Allow re-start only if caller explicitly wants to force — for now block
            pass

    dispatched = False
    dispatch_info: dict[str, Any] = {}
    try:
        from precompute.workers.celery_tasks import dispatch_armor_pipeline  # type: ignore

        result = dispatch_armor_pipeline()
        dispatch_info = {"celery": True, "result": str(result) if result else "enqueued"}
        dispatched = True
    except ImportError:
        dispatch_info = {"celery": False, "reason": "precompute.workers.celery_tasks not available"}
    except Exception as exc:
        dispatch_info = {"celery": False, "reason": str(exc)}

    groups = _empty_groups()
    now = datetime.now(UTC)
    status_obj = PrecomputeStatusResponse(
        overall_status=JobStatus.RUNNING,
        current_group=SymbolGroup.A,
        total_symbols=0,
        completed_symbols=0,
        failed_symbols=0,
        progress_percent=0.0,
        current_symbol=None,
        estimated_remaining_seconds=None,
        last_update=now,
        groups=groups,
    )
    raw_status = json.loads(status_obj.model_dump_json())
    await _save_status(raw_status)
    try:
        mgr = get_armor_ws_manager()
        await mgr.broadcast_raw("PRECOMPUTATION_STARTED", {"timestamp": _now_iso(), "dispatched": dispatched})
    except Exception:
        pass
    return ApiResponse[dict[str, Any]](
        success=True,
        data={"status": raw_status, "dispatch": dispatch_info},
        message="Precomputation started" if dispatched else "Precomputation marked RUNNING (Celery not available)",
    )


@router.get("/status", summary="وضعیت زنده پیش‌محاسبه")
async def get_precompute_status() -> ApiResponse[dict[str, Any]]:
    status = await _load_status()
    try:
        mgr = get_armor_ws_manager()
        status["_ws_connections"] = mgr.connection_count()
    except Exception:
        pass
    return ApiResponse[dict[str, Any]](success=True, data=status)


# ── Router for /dashboard/ready ─────────────────────────────────
dashboard_router = APIRouter(tags=["Armor Dashboard"])


@dashboard_router.get("/ready", summary="نمادهای آماده داشبورد (Hot cache)")
async def get_dashboard_ready() -> ApiResponse[list[dict[str, Any]]]:
    results = await _load_all_results()
    for r in results:
        r["_is_stale"] = _api_is_stale(r.get("expires_at"))
        r["is_stale"] = r["_is_stale"]
    try:
        results.sort(key=lambda x: float(x.get("armor_score", 0) or 0), reverse=True)
    except Exception:
        pass
    return ApiResponse[list[dict[str, Any]]](success=True, data=results)


# ── Router for /symbols/{symbol}/summary ───────────────────────
symbols_router = APIRouter(tags=["Armor Symbols"])


@symbols_router.get("/{symbol}/summary", summary="خلاصه نماد (با برچسب STALE)")
async def get_symbol_summary(
    symbol: str = Path(..., description="نماد، مثلا فملی"),
) -> ApiResponse[dict[str, Any]]:
    result = await _load_single_result(symbol)
    if result is None:
        cache = get_cache()
        if cache.is_connected:
            try:
                alt = await cache.get(f"armor:symbol:{symbol}")
                if isinstance(alt, dict) and "symbol" in alt:
                    result = alt
                elif isinstance(alt, str):
                    result = json.loads(alt)
            except Exception:
                pass
    if result is None:
        raise HTTPException(
            status_code=404,
            detail={"message": f"Symbol {symbol} not found in Hot cache", "symbol": symbol},
        )
    is_stale = _api_is_stale(result.get("expires_at"))
    try:
        validated = SymbolComputationResult.model_validate(result)
        payload = json.loads(validated.model_dump_json())
        payload["is_stale"] = is_stale
        payload["_is_stale"] = is_stale
        if is_stale:
            payload["_stale_reason"] = f"expires_at {result.get('expires_at')} is in the past"
    except Exception:
        payload = dict(result)
        payload["is_stale"] = is_stale
        payload["_is_stale"] = is_stale
    payload["_cache"] = "redis:hot"
    payload["_stale"] = is_stale
    if is_stale:
        payload["_label"] = JobStatus.STALE.value
    return ApiResponse[dict[str, Any]](success=True, data=payload)
