"""
precompute/workers/celery_tasks.py — priority-queued precompute pipeline.

Groups A/B/C run in priority order (A first). With Celery installed the three
groups are dispatched to ``queue_group_a/b/c`` and ``finalize`` closes the run;
without Celery (the current environment) the same functions run sequentially
in-process via ``dispatch_armor_pipeline``.

Decoupling (Zero Conflict Policy):
  * Imports ONLY ``contracts`` (read-only) and local ``precompute.*`` modules.
  * Reads raw quotes from the ingestion hot layer keys
    (``ingestion:hot:scan:latest`` + ``ingestion:hot:quote:{symbol}``).
  * Writes per-symbol results to ``precompute:result:{symbol}`` — exactly the
    key api/routers/precompute_router reads for GET /symbols/{symbol}/summary.
  * Publishes the 4 contract events (contracts/events.md) onto the
    ``precompute:events`` Redis channel; the api ws_manager subscribes to it.
"""
from __future__ import annotations

import json
import logging
import math
import os
import time
from datetime import UTC, datetime, timedelta
from typing import Any

from contracts.events import (
    PRECOMPUTATION_COMPLETED,
    PRECOMPUTATION_GROUP_COMPLETED,
    PRECOMPUTATION_PROGRESS,
    SYMBOL_RESULT_UPDATED,
)
from contracts.schemas import SymbolGroup

from .. import redis_client
from ..config import load_config
from ..dri_engine import DRISignals, age_from_iso, compute_dri
from ..missing_data_auditor import audit_batch
from ..classifier import classify_from_dicts

logger = logging.getLogger("precompute.workers.celery_tasks")

_config = load_config()

# Event transport selection for _emit inside a running loop:
#   auto   — API broadcast funnel when the API-side core.cache is connected
#            (that is the API process), else this scope's own Redis transport
#            (a Celery worker runs asyncio.run() loops but never connects
#            core.cache, so every funnel publish would silently no-op)
#   funnel — force the API broadcast funnel (unit tests simulating the API
#            process without a Redis connection)
#   redis  — force the direct precompute transport
EMIT_MODE = os.getenv("PRECOMPUTE_EMIT_MODE", "auto")

QUEUE_A = _config.queue_a
QUEUE_B = _config.queue_b
QUEUE_C = _config.queue_c

# Ingestion hot-layer keys (read-only contract with ingestion scope).
_INGEST_SCAN_KEY = "ingestion:hot:scan:latest"
_INGEST_QUOTE_KEY = "ingestion:hot:quote:{symbol}"


# ── Celery wiring (lazy; degrades to sync when Celery is absent) ──────────
_celery_app = None


def _get_celery_app():
    global _celery_app
    if _celery_app is not None:
        return _celery_app
    try:
        from celery import Celery  # type: ignore

        app = Celery("armor_precompute", broker=_config.redis_url, backend=_config.redis_url)
        app.conf.update(
            task_serializer="json",
            accept_content=["json"],
            result_serializer="json",
            timezone="Asia/Tehran",
            enable_utc=True,
            task_acks_late=True,
            worker_prefetch_multiplier=1,
            task_routes={
                "precompute.workers.celery_tasks.compute_group_a": {"queue": QUEUE_A},
                "precompute.workers.celery_tasks.compute_group_b": {"queue": QUEUE_B},
                "precompute.workers.celery_tasks.compute_group_c": {"queue": QUEUE_C},
            },
        )
        _celery_app = app
        return app
    except ImportError:
        logger.warning("Celery not installed — precompute runs via sync fallback")
        return None
    except Exception as exc:  # noqa: BLE001
        logger.warning("Celery init failed: %s", exc)
        return None


def _maybe_task(queue: str, name: str):
    """Wrap as a Celery task if available, else a plain callable with .delay."""
    import functools

    app = _get_celery_app()

    def decorator(fn):
        if app is not None:
            return app.task(name=name, queue=queue, bind=True)(fn)

        @functools.wraps(fn)  # keeps __wrapped__ so signatures stay inspectable
        def _plain(self=None, *a, **kw):
            return fn(None, *a, **kw)

        _plain.delay = lambda *a, **kw: _plain(None, *a, **kw)  # type: ignore[attr-defined]
        _plain.apply_async = lambda kwargs=None, **_: _plain(None, **(kwargs or {}))  # type: ignore[attr-defined]
        return _plain

    return decorator


# ── Event + result publishing (contract-bound, never imports api at import time) ─
async def _emit(event_type: str, payload: dict) -> None:
    """Deliver a contract event to the API layer.

    Two transports, chosen by context:
      * running event loop (API sync-fallback path) -> api.ws_manager
        broadcast funnel: feeds the job_state machine behind
        GET /precompute/status AND WebSocket dashboard clients, and fans
        out to Redis for other processes.  Runtime lazy import only —
        the precompute scope keeps zero import-time coupling to api.
      * no loop (real Celery worker) -> Redis publish on the events
        channel; the API's ws_manager subscriber funnels it onward.
    """
    import asyncio

    try:
        asyncio.get_running_loop()
    except RuntimeError:
        await redis_client.publish_event(event_type, payload, _config)
        return

    # Inside a running loop: decide by *where* we are, not just by loop
    # presence (see EMIT_MODE above).
    from core.cache import get_cache

    use_funnel = EMIT_MODE == "funnel" or (EMIT_MODE == "auto" and get_cache().is_connected)
    if use_funnel:
        try:
            from api.ws_manager import get_armor_ws_manager

            await get_armor_ws_manager().broadcast_event_awaited(event_type, payload)
            return
        except Exception:  # noqa: BLE001 — event delivery must never break computation
            pass
    await redis_client.publish_event(event_type, payload, _config)


async def _store(symbol: str, result: dict) -> None:
    await redis_client.save_result(symbol, result, _config)


# ── Core per-symbol computation ───────────────────────────────────────────
def compute_single_symbol(row: dict[str, Any], group: str, audit_result: Any | None = None) -> dict[str, Any]:
    """Compute armor_score + DRI for one symbol from its raw snapshot.

    Uses only precompute-local engines. Deterministic proxies keep dev/test
    runs valid when full market depth is unavailable.
    """
    from ..missing_data_auditor import audit_row

    audit = audit_result or audit_row(row)
    p = audit.patched_row

    price_last = float(p.get("price_last") or p.get("price") or 1000)
    trade_value = float(p.get("trade_value") or p.get("value") or 5e11)
    trade_volume = float(p.get("trade_volume") or p.get("volume") or 1e6)
    free_float = float(p.get("free_float_pct") or 25)

    low = float(p.get("price_lowest_allowed") or price_last * 0.95)
    high = float(p.get("price_highest_allowed") or price_last * 1.05)
    band_pos = (price_last - low) / max(1.0, high - low)
    technical = max(0.0, min(100.0, 50 + (band_pos - 0.5) * 40 + (5 if trade_value > 1e12 else -5)))
    liquidity = max(0.0, min(100.0, 0.5 * free_float * 2 + math.log10(max(trade_value, 1e9) / 1e9) * 10))
    money_flow = max(0.0, min(100.0, 50 + math.log10(max(trade_volume, 1e3) / 1e3) * 8))
    armor = max(0.0, min(100.0, round(0.40 * technical + 0.35 * liquidity + 0.25 * money_flow, 1)))

    age = age_from_iso(p.get("fetched_at") or p.get("updated_at"))
    signals = DRISignals(
        completeness=audit.completeness,
        age_seconds=age if age is not None else 10.0,
        is_market_open=False,  # background tasks are conservative
        price_in_band=(low <= price_last <= high) if low and high else None,
        volume_value_coherent=(trade_value > 0 and trade_volume > 0),
        source_count=1,
        max_sources=3,
        has_critical_missing=audit.has_critical,
    )
    dri_res = compute_dri(signals)

    now = datetime.now(UTC)
    return {
        "symbol": p.get("symbol") or row.get("symbol") or "UNKNOWN",
        "group": group,
        "last_price": price_last,
        "closing_price": float(p.get("closing_price") or price_last),
        "technical_score": round(technical, 1),
        "liquidity_score": round(liquidity, 1),
        "money_flow_score": round(money_flow, 1),
        "armor_score": armor,
        "data_dri": dri_res.dri,
        "is_unreliable": dri_res.is_unreliable,
        "red_flags": dri_res.red_flags + audit.red_flags,
        "calculated_at": now.isoformat(),
        "expires_at": (now + timedelta(hours=1)).isoformat(),
        "version": "v4.0",
    }


async def _run_group(symbols: list[dict[str, Any]], group: str, job_id: str | None = None) -> dict[str, Any]:
    """Compute one group, persist results, broadcast contract events."""
    total = len(symbols)
    completed = failed = 0
    start = time.time()
    dri_sum = 0.0

    try:
        audits, _ = audit_batch(symbols) if symbols else ([], {})
    except Exception as exc:  # noqa: BLE001 — one bad batch must not kill the group
        logger.warning("audit_batch failed for group %s (job %s): %s", group, job_id, exc)
        audits = [None] * len(symbols)

    for idx, row in enumerate(symbols):
        sym = row.get("symbol") or f"sym-{idx}"
        try:
            audit = audits[idx] if idx < len(audits) else None
            result = compute_single_symbol(row, group, audit_result=audit)
            await _store(sym, result)
            await _emit(
                "SYMBOL_RESULT_UPDATED",
                SYMBOL_RESULT_UPDATED(
                    symbol=result["symbol"],
                    group=group,
                    armor_score=result["armor_score"],
                    data_dri=result["data_dri"],
                    is_unreliable=result["is_unreliable"],
                ).model_dump(),
            )
            completed += 1
            dri_sum += result["data_dri"]
        except Exception as exc:  # noqa: BLE001
            logger.warning("compute failed for %s [%s]: %s", sym, group, exc)
            failed += 1

        if (idx + 1) % _config.progress_every == 0 or (idx + 1) == total:
            await _emit(
                "PRECOMPUTATION_PROGRESS",
                PRECOMPUTATION_PROGRESS(
                    group=group,
                    completed=idx + 1,
                    total=total,
                    percent=round((idx + 1) / max(1, total) * 100, 1),
                    current_symbol=sym,
                ).model_dump(),
            )

    duration = round(time.time() - start, 1)
    avg_dri = round(dri_sum / completed, 1) if completed else 0.0
    await _emit(
        "PRECOMPUTATION_GROUP_COMPLETED",
        PRECOMPUTATION_GROUP_COMPLETED(
            group=group,
            total_processed=total,
            failed=failed,
            timestamp=datetime.now(UTC).isoformat(),
        ).model_dump(),
    )
    return {
        "group": group,
        "total_processed": total,
        "completed": completed,
        "failed": failed,
        "avg_dri": avg_dri,
        "duration_seconds": duration,
    }


# ── Group task entrypoints (Celery or sync) ───────────────────────────────
@_maybe_task(QUEUE_A, "precompute.workers.celery_tasks.compute_group_a")
def compute_group_a(self=None, symbols: list[dict[str, Any]] | None = None, job_id: str | None = None) -> dict[str, Any]:
    return {"_group_A": _run_sync(symbols or [], "A", job_id)}


@_maybe_task(QUEUE_B, "precompute.workers.celery_tasks.compute_group_b")
def compute_group_b(self=None, prev_result: dict[str, Any] | None = None, symbols: list[dict[str, Any]] | None = None, job_id: str | None = None) -> dict[str, Any]:
    return {**(prev_result or {}), "_group_B": _run_sync(symbols or [], "B", job_id)}


@_maybe_task(QUEUE_C, "precompute.workers.celery_tasks.compute_group_c")
def compute_group_c(self=None, prev_result: dict[str, Any] | None = None, symbols: list[dict[str, Any]] | None = None, job_id: str | None = None) -> dict[str, Any]:
    return {**(prev_result or {}), "_group_C": _run_sync(symbols or [], "C", job_id)}


@_maybe_task(QUEUE_A, "precompute.workers.celery_tasks.finalize_precompute")
def finalize_precompute(self=None, prev_result: dict[str, Any] | None = None, job_id: str | None = None) -> dict[str, Any]:
    payload = _finalize(prev_result, job_id)
    # Celery workers run this in a sync context: emit the terminal event here
    # too, or the frontend/sound trigger never sees PRECOMPUTATION_COMPLETED.
    # Inside a running loop the async dispatch path owns the emit (creating a
    # coroutine we cannot await here would trigger RuntimeWarnings).
    import asyncio

    try:
        asyncio.get_running_loop()
    except RuntimeError:
        try:
            asyncio.run(_emit("PRECOMPUTATION_COMPLETED", payload))
        except Exception:  # noqa: BLE001 - best-effort
            pass
    return payload


def _run_sync(symbols: list[dict[str, Any]], group: str, job_id: str | None) -> dict[str, Any]:
    """Bridge the async group runner to sync task signatures.

    Never calls run_until_complete on an ALREADY-RUNNING loop (that raises
    RuntimeError); callers inside a live loop must use the async dispatch
    path (``dispatch_armor_pipeline_async``) instead.
    """
    import asyncio

    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(_run_group(symbols, group, job_id))
    raise RuntimeError(
        "_run_sync cannot block a running event loop — "
        "await dispatch_armor_pipeline_async() from async contexts"
    )


def _finalize(prev_result: dict[str, Any] | None, job_id: str | None) -> dict[str, Any]:
    total = success = failed = 0
    per_group: dict[str, Any] = {}
    if isinstance(prev_result, dict):
        for g in ("A", "B", "C"):
            gs = prev_result.get(f"_group_{g}")
            if isinstance(gs, dict):
                per_group[g] = gs
                total += int(gs.get("total_processed") or 0)
                success += int(gs.get("completed") or 0)
                failed += int(gs.get("failed") or 0)
    overall = "SUCCESS" if failed == 0 else ("PARTIAL" if success > 0 else "FAILED")
    avg_dri = round(sum(float(gs.get("avg_dri") or 0) for gs in per_group.values()) / max(1, len(per_group)), 1)
    payload = PRECOMPUTATION_COMPLETED(
        total=total,
        success=success,
        failed=failed,
        avg_dri=avg_dri,
        duration_seconds=round(sum(float(gs.get("duration_seconds") or 0) for gs in per_group.values()), 1),
        timestamp=datetime.now(UTC).isoformat(),
    ).model_dump()
    payload["job_id"] = job_id
    payload["overall_status"] = overall
    payload["groups"] = per_group
    return payload


async def _finalize_async(prev_result: dict[str, Any] | None, job_id: str | None) -> dict[str, Any]:
    """Async finalize: aggregates the chain context and emits the terminal
    PRECOMPUTATION_COMPLETED (used by the API-process dispatch path)."""
    payload = _finalize(prev_result, job_id)
    await _emit("PRECOMPUTATION_COMPLETED", payload)
    return payload


# ── Orchestrator ──────────────────────────────────────────────────────────
async def dispatch_armor_pipeline_async(
    symbols_by_group: dict[str, list[dict[str, Any]]] | None = None,
    job_id: str | None = None,
) -> dict[str, Any]:
    """API-process path: run A->B->C->finalize inline on the running loop.

    Every event flows through _emit -> api.ws_manager -> job_state + WS
    clients, so GET /precompute/status tracks the run live.  Used by the
    precompute router when Celery is not configured (sync fallback).
    """
    groups = symbols_by_group or {"A": [], "B": [], "C": []}
    job_id = job_id or f"precompute-{datetime.now(UTC).strftime('%Y%m%d-%H%M%S')}"
    app = _get_celery_app()
    if app is not None:
        return dispatch_armor_pipeline(groups, job_id)  # delegate to Celery path

    logger.info("Celery unavailable — running Armor pipeline on the event loop (job %s)", job_id)
    ra = await _run_group(groups.get("A", []), "A", job_id)
    rb = await _run_group(groups.get("B", []), "B", job_id)
    rc = await _run_group(groups.get("C", []), "C", job_id)
    return await _finalize_async({"_group_A": ra, "_group_B": rb, "_group_C": rc}, job_id)


def dispatch_armor_pipeline(
    symbols_by_group: dict[str, list[dict[str, Any]]] | None = None,
    job_id: str | None = None,
) -> dict[str, Any]:
    """Sync orchestrator (Celery path, or off-loop fallback for tests/CLI)."""
    groups = symbols_by_group or {"A": [], "B": [], "C": []}
    total_all = sum(len(groups.get(g, [])) for g in ("A", "B", "C"))
    job_id = job_id or f"precompute-{datetime.now(UTC).strftime('%Y%m%d-%H%M%S')}"
    app = _get_celery_app()

    if app is None:
        # Off-loop context (no Celery): block on the pipeline.  Inside a
        # running loop this would deadlock/crash — callers there must await
        # dispatch_armor_pipeline_async() instead.
        import asyncio

        try:
            asyncio.get_running_loop()
        except RuntimeError:
            logger.info("Celery unavailable — running pipeline synchronously (job %s)", job_id)
            return _run_pipeline_blocking(groups, job_id)
        raise RuntimeError(
            "dispatch_armor_pipeline() cannot block a running event loop — "
            "await dispatch_armor_pipeline_async() from async contexts"
        )

    try:
        from celery import chain  # type: ignore

        workflow = chain(
            compute_group_a.s(symbols=groups.get("A", []), job_id=job_id),
            compute_group_b.s(symbols=groups.get("B", []), job_id=job_id),
            compute_group_c.s(symbols=groups.get("C", []), job_id=job_id),
            finalize_precompute.s(job_id=job_id),
        )
        result = workflow.apply_async()
        chain_id = result.id if hasattr(result, "id") else None
        logger.info("Pipeline dispatched via Celery chain (job %s): %s", job_id, chain_id)
        return {"celery": True, "job_id": job_id, "chain_id": chain_id}
    except Exception as exc:  # noqa: BLE001
        # Broker unreachable: run inline instead of recursing back into the
        # Celery branch, which would loop forever.
        logger.warning("Celery dispatch failed, falling back to inline run: %s", exc)
        return _run_pipeline_blocking(groups, job_id)


def _run_pipeline_blocking(groups: dict[str, list[dict[str, Any]]], job_id: str) -> dict[str, Any]:
    """A->B->C->finalize on fresh private loops; emits every contract event."""
    import asyncio

    ra = _run_sync(groups.get("A", []), "A", job_id)
    rb = _run_sync(groups.get("B", []), "B", job_id)
    rc = _run_sync(groups.get("C", []), "C", job_id)
    return asyncio.run(
        _finalize_async({"_group_A": ra, "_group_B": rb, "_group_C": rc}, job_id)
    )


# ── Ingestion hot-layer loader (decoupled read) ───────────────────────────
async def load_symbols_from_ingestion(user_basket: set[str] | None = None) -> dict[str, list[dict[str, Any]]]:
    """Read the latest scanner snapshot from the ingestion hot layer and split
    into A/B/C groups via the precompute classifier.

    Returns {group: [raw_symbol_row, ...]}. Empty when Redis/ingestion is down
    (caller should fall back to its own symbol source).
    """
    try:
        client = redis_client.get_redis(_config)
        scan = await client.get(_INGEST_SCAN_KEY)
        if not scan:
            return {"A": [], "B": [], "C": []}
        scan_meta = json.loads(scan)
        symbols = scan_meta.get("symbols", [])
        rows: list[dict[str, Any]] = []
        for sym in symbols:
            raw = await client.get(_INGEST_QUOTE_KEY.format(symbol=sym))
            if raw:
                rows.append(json.loads(raw))
        if not rows:
            return {"A": [], "B": [], "C": []}
        grouping = classify_from_dicts(rows, user_basket=user_basket)
        out: dict[str, list[dict[str, Any]]] = {"A": [], "B": [], "C": []}
        for row in rows:
            grp = grouping.get(row.get("symbol", ""), SymbolGroup.C)
            out[grp.value].append(row)
        return out
    except Exception as exc:  # noqa: BLE001
        logger.warning("Failed to load symbols from ingestion hot layer: %s", exc)
        return {"A": [], "B": [], "C": []}
