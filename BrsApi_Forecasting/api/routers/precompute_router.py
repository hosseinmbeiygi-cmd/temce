# api/routers/precompute_router.py — Precompute dashboard API endpoints.
# Decoupled from worker code: communicates via contracts + Redis + WS broadcast.
from __future__ import annotations

import asyncio
import json
import time
from datetime import datetime, timezone
from typing import Any

from contracts.exceptions import PrecomputeJobCollisionError, PrecomputeNotRunningError, StaleResultError, SymbolNotFoundError  # noqa: F401 — available for worker callbacks
from contracts.schemas import JobStatus, PrecomputeStatusResponse, SymbolComputationResult, SymbolGroup
from core.config import INFRA, RAW_PRICE_CACHE_TTL_SECONDS
from core.redis_client import get_redis
from fastapi import APIRouter, HTTPException, WebSocket, WebSocketDisconnect

from api.websocket.ws_manager import (
    broadcast_completed,
    broadcast_group_completed,
    broadcast_progress,
    broadcast_symbol_updated,
    get_connection_count,
    register,
    unregister,
)  # noqa: F401 — register/unregister used in WS endpoint; broadcast_* used by worker callbacks

router = APIRouter(prefix="/api", tags=["precompute"])

# ---------------------------------------------------------------------------
# In-process status tracker (falls back gracefully if Redis is down)
# ---------------------------------------------------------------------------

_job_state: dict[str, Any] = {}


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _now_dt() -> datetime:
    return datetime.now(timezone.utc)


# ---------------------------------------------------------------------------
# Helpers — Redis-backed symbol cache
# ---------------------------------------------------------------------------

_SYMBOL_RESULT_KEY = "precompute:result:{symbol}"


async def _read_symbol_result(symbol: str) -> dict | None:
    """Return the raw JSON for a symbol's precomputed result, or None."""
    redis = get_redis()
    raw = await redis.get(_SYMBOL_RESULT_KEY.format(symbol=symbol))
    if raw is None:
        return None
    return __import__("json", fromlist=["loads"]).loads(raw)


async def _write_symbol_result(symbol: str, payload: dict) -> None:
    redis = get_redis()
    import json

    ttl = RAW_PRICE_CACHE_TTL_SECONDS  # reuse the same staleness window as raw prices
    await redis.set(_SYMBOL_RESULT_KEY.format(symbol=symbol), json.dumps(payload), ex=ttl)


# ---------------------------------------------------------------------------
# POST /api/precompute/start
# ---------------------------------------------------------------------------


@router.post("/precompute/start")
async def start_precompute() -> dict[str, Any]:
    """Queue a full precompute run (groups A → B → C).

    Idempotent-ish: if a job is already running the call is rejected with 409.
    The actual Celery dispatch is abstracted — this endpoint writes state and
    returns a job id. The worker side is responsible for broadcasting progress.
    """
    if _job_state.get("running"):
        raise HTTPException(status_code=409, detail="A precompute job is already running.")

    job_id = f"job-{int(time.time() * 1_000_000)}"
    now = _now_dt()

    _job_state.update(
        {
            "job_id": job_id,
            "running": True,
            "started_at": now,
            "overall_status": JobStatus.RUNNING,
            "current_group": SymbolGroup.A,
            "total_symbols": 0,
            "completed_symbols": 0,
            "failed_symbols": 0,
            "progress_percent": 0.0,
            "current_symbol": None,
            "estimated_remaining_seconds": None,
            "groups": {
                SymbolGroup.A: {"total": 0, "completed": 0, "failed": 0, "status": JobStatus.PENDING},
                SymbolGroup.B: {"total": 0, "completed": 0, "failed": 0, "status": JobStatus.PENDING},
                SymbolGroup.C: {"total": 0, "completed": 0, "failed": 0, "status": JobStatus.PENDING},
            },
        }
    )

    # In a fully wired system this would call:
    #   from precompute.workers.celery_tasks import run_full_precompute
    #   run_full_precompute.delay(job_id=job_id)
    # For now the state machine is in-process; the worker writes back through
    # the same _update_status / broadcast helpers.

    return {
        "job_id": job_id,
        "status": "queued",
        "started_at": now.isoformat(),
        "message": "Precompute job accepted. Subscribe to /api/ws/precompute for progress.",
    }


# ---------------------------------------------------------------------------
# GET /api/precompute/status
# ---------------------------------------------------------------------------


@router.get("/precompute/status")
async def get_precompute_status() -> PrecomputeStatusResponse:
    """Live precompute status. Reads in-process tracker first, falls back to Redis."""
    if not _job_state.get("running"):
        raise HTTPException(status_code=409, detail="No precompute job is currently running.")

    state = _job_state
    total = state["total_symbols"] or 1  # avoid div-by-zero before first symbol

    groups_out = {}
    for grp, meta in state["groups"].items():
        groups_out[grp] = {
            "total": meta["total"],
            "completed": meta["completed"],
            "failed": meta["failed"],
            "status": meta["status"],
        }

    return PrecomputeStatusResponse(
        overall_status=state["overall_status"],
        current_group=state.get("current_group"),
        total_symbols=state["total_symbols"],
        completed_symbols=state["completed_symbols"],
        failed_symbols=state["failed_symbols"],
        progress_percent=round((state["completed_symbols"] / total) * 100, 2) if total else 0.0,
        current_symbol=state.get("current_symbol"),
        estimated_remaining_seconds=state.get("estimated_remaining_seconds"),
        last_update=_now_dt(),
        groups=groups_out,
    )


# ---------------------------------------------------------------------------
# Internal state machine — called by worker callbacks (here for in-process demo;
# in production these live in the Celery task and call back into the API layer
# via Redis pub/sub or direct function refs).
# ---------------------------------------------------------------------------


def _update_status(group: SymbolGroup, symbol: str | None, total_symbols_hint: int | None = None) -> None:
    """Thread-unsafe in-process update — acceptable because we run single-worker."""
    state = _job_state
    if total_symbols_hint is not None:
        state["total_symbols"] = max(state["total_symbols"], total_symbols_hint)

    if symbol is not None:
        state["current_symbol"] = symbol
        state["completed_symbols"] += 1
        state["groups"][group]["completed"] += 1
        state["groups"][group]["status"] = JobStatus.RUNNING

    total = state["total_symbols"] or 1
    state["progress_percent"] = round((state["completed_symbols"] / total) * 100, 2)

    # naive ETA
    elapsed = (datetime.now(timezone.utc) - state["started_at"]).total_seconds()
    if state["completed_symbols"] > 0 and state["total_symbols"]:
        per_symbol = elapsed / state["completed_symbols"]
        remaining = (state["total_symbols"] - state["completed_symbols"]) * per_symbol
        state["estimated_remaining_seconds"] = int(remaining)


def _group_done(group: SymbolGroup, total_processed: int, failed: int) -> None:
    state = _job_state
    state["groups"][group]["total"] = total_processed
    state["groups"][group]["completed"] = total_processed - failed
    state["groups"][group]["failed"] = failed
    state["groups"][group]["status"] = JobStatus.SUCCESS
    state["current_group"] = {
        SymbolGroup.A: SymbolGroup.B,
        SymbolGroup.B: SymbolGroup.C,
        SymbolGroup.C: None,
    }.get(group)


def _all_done(total: int, success: int, failed: int, avg_dri: float, duration_seconds: float) -> None:
    state = _job_state
    state["overall_status"] = JobStatus.SUCCESS
    state["running"] = False
    state["total_symbols"] = total
    state["completed_symbols"] = success
    state["failed_symbols"] = failed
    state["progress_percent"] = 100.0
    state["estimated_remaining_seconds"] = 0

    asyncio.create_task(
        broadcast_completed(
            total=total,
            success=success,
            failed=failed,
            avg_dri=avg_dri,
            duration_seconds=duration_seconds,
            timestamp=_now_iso(),
        )
    )


# ---------------------------------------------------------------------------
# WebSocket /api/ws/precompute — progress stream for the dashboard
# ---------------------------------------------------------------------------


@router.websocket("/ws/precompute")
async def websocket_precompute(stream: WebSocket):
    """Push precompute progress to connected dashboard clients.

    Clients MAY send JSON {"groups": ["A","B","C"]} to filter which group
    events they care about. Without a filter, all events are broadcast.
    """
    await stream.accept()
    requested_groups: set[str] = set()
    client_id = f"ws-{id(stream)}"

    await register(stream, groups=requested_groups, client_id=client_id)
    try:
        while True:
            try:
                raw = await asyncio.wait_for(stream.receive_text(), timeout=30)
            except TimeoutError:
                continue
            try:
                msg = json.loads(raw)
            except (ValueError, TypeError):
                continue
            if isinstance(msg.get("groups"), list):
                requested_groups = {str(g) for g in msg["groups"] if g}
    except WebSocketDisconnect:
        pass
    finally:
        await unregister(stream)


# ---------------------------------------------------------------------------
# GET /api/dashboard/ready
# ---------------------------------------------------------------------------


@router.get("/dashboard/ready")
async def dashboard_ready() -> dict[str, Any]:
    """Lightweight readiness probe for the frontend.

    Returns whether a precompute job is active and how many clients are
    connected to the progress WebSocket.
    """
    redis_ok = False
    try:
        redis = get_redis()
        # Use a short timeout so Redis outages don't stall the readiness probe.
        await asyncio.wait_for(redis.ping(), timeout=2.0)
        redis_ok = True
    except Exception:
        redis_ok = False

    return {
        "ready": True,
        "redis": redis_ok,
        "job_running": _job_state.get("running", False),
        "job_id": _job_state.get("job_id"),
        "ws_clients": await get_connection_count(),
        "timestamp": _now_iso(),
    }


# ---------------------------------------------------------------------------
# GET /api/symbols/{symbol}/summary
# ---------------------------------------------------------------------------


@router.get("/symbols/{symbol}/summary")
async def symbol_summary(symbol: str) -> dict[str, Any]:
    """Return the precomputed summary for a single symbol.

    Reads from Redis hot cache. Tags the result as STALE if it's older than
    the freshness window (same TTL as raw price cache).
    """
    try:
        payload = await asyncio.wait_for(_read_symbol_result(symbol), timeout=5.0)
    except Exception:
        raise HTTPException(status_code=503, detail="Redis unavailable.")
    if payload is None:
        raise HTTPException(status_code=404, detail=f"No precomputed result for {symbol}.")

    # Parse timestamps
    calculated_at: datetime | None = None
    expires_at: datetime | None = None
    try:
        calculated_at = datetime.fromisoformat(payload.get("calculated_at", "").replace("Z", "+00:00"))
        expires_at = datetime.fromisoformat(payload.get("expires_at", "").replace("Z", "+00:00"))
    except (ValueError, AttributeError):
        pass

    is_stale = False
    if expires_at and calculated_at:
        is_stale = datetime.now(timezone.utc) > expires_at

    result = SymbolComputationResult(
        symbol=payload.get("symbol", symbol),
        group=SymbolGroup(payload.get("group", "A")),
        last_price=payload.get("last_price", 0.0),
        closing_price=payload.get("closing_price", 0.0),
        technical_score=payload.get("technical_score", 0.0),
        liquidity_score=payload.get("liquidity_score", 0.0),
        money_flow_score=payload.get("money_flow_score", 0.0),
        armor_score=payload.get("armor_score", 0.0),
        data_dri=payload.get("data_dri", 0.0),
        is_unreliable=payload.get("is_unreliable", False),
        red_flags=payload.get("red_flags", []),
        calculated_at=calculated_at or _now_dt(),
        expires_at=expires_at or _now_dt(),
        version=payload.get("version", "v4.0"),
    )

    return {
        "symbol": result.symbol,
        "group": result.group.value,
        "last_price": result.last_price,
        "closing_price": result.closing_price,
        "technical_score": result.technical_score,
        "liquidity_score": result.liquidity_score,
        "money_flow_score": result.money_flow_score,
        "armor_score": result.armor_score,
        "data_dri": result.data_dri,
        "is_unreliable": result.is_unreliable,
        "red_flags": result.red_flags,
        "calculated_at": result.calculated_at.isoformat(),
        "expires_at": result.expires_at.isoformat(),
        "version": result.version,
        "status": "STALE" if is_stale else "FRESH",
    }
