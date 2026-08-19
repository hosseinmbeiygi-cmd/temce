from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from core.config import settings
from core.database import get_session
from core.db_utils import safe_row_str
from core.logging import get_logger
from schemas.common.responses import ApiResponse

logger = get_logger(__name__)

router = APIRouter()


# ──────────────────────────────────────────────
#  BrsApi Scheduler Jobs Management
#  (Enable/disable scheduler jobs via Web UI)
# ──────────────────────────────────────────────


def _get_brsapi_registry():
    """Get the BrsApi job registry singleton."""
    from brsapi.jobs.registry import get_brsapi_job_registry
    return get_brsapi_job_registry()


@router.get(
    "/scheduler",
    summary="List BrsApi scheduler jobs",
    description="List all BrsApi scheduler jobs with their enabled/disabled status, cron schedule, and description",
)
async def list_scheduler_jobs() -> ApiResponse[list[dict[str, Any]]]:
    """List all BrsApi sync jobs with their status."""
    try:
        registry = _get_brsapi_registry()
        jobs = registry.list_all_jobs()

        # Augment with APScheduler runtime info if available
        if registry.scheduler:
            for job_info in jobs:
                aps_job = registry.scheduler.get_job(job_info["name"])
                if aps_job:
                    job_info["next_run_time"] = (
                        aps_job.next_run_time.isoformat() if aps_job.next_run_time else None
                    )
                else:
                    job_info["next_run_time"] = None
        else:
            for job_info in jobs:
                job_info["next_run_time"] = None

        enabled_count = sum(1 for j in jobs if j["enabled"])
        return ApiResponse(
            success=True,
            data={
                "jobs": jobs,
                "total": len(jobs),
                "enabled": enabled_count,
                "disabled": len(jobs) - enabled_count,
            },
        )
    except Exception as exc:
        logger.exception("Failed to list scheduler jobs")
        return ApiResponse(success=False, error={"message": str(exc)}, data={"jobs": [], "total": 0, "enabled": 0, "disabled": 0})


@router.post(
    "/scheduler/{job_name}/toggle",
    summary="Toggle a scheduler job",
    description="Enable or disable a BrsApi scheduler job at runtime. Changes take effect immediately.",
)
async def toggle_scheduler_job(job_name: str) -> ApiResponse[dict[str, Any]]:
    """Toggle a job's enabled/disabled status."""
    registry = _get_brsapi_registry()
    job = registry.get(job_name)
    if job is None:
        raise HTTPException(status_code=404, detail=f"Unknown scheduler job: {job_name}")
    try:
        result = registry.toggle_job(job_name)
        return ApiResponse(success=True, data=result)
    except Exception as exc:
        logger.exception("Failed to toggle job '%s'", job_name)
        raise HTTPException(status_code=500, detail=str(exc))


@router.post(
    "/scheduler/{job_name}/run",
    summary="Run a scheduler job now",
    description="Trigger an immediate run of a BrsApi scheduler job (bypasses the scheduler).",
)
async def run_scheduler_job(job_name: str) -> ApiResponse[dict[str, Any]]:
    """Trigger an immediate run of a specific scheduler job."""
    registry = _get_brsapi_registry()
    job = registry.get(job_name)
    if job is None:
        raise HTTPException(status_code=404, detail=f"Unknown scheduler job: {job_name}")
    try:
        result = await registry.run_job_now(job_name)
        return ApiResponse(success=result.get("success", False), data=result)
    except Exception as exc:
        logger.exception("Failed to run job '%s'", job_name)
        raise HTTPException(status_code=500, detail=str(exc))


# ──────────────────────────────────────────────
#  Job Run History (existing)
# ──────────────────────────────────────────────


JOBS_LIST_QUERY = """
    SELECT id, job_type, status, progress_pct,
           started_at, completed_at, duration_seconds,
           error_message, triggered_by, created_at
    FROM job_runs
    WHERE 1=1
      {status_filter}
      {type_filter}
    ORDER BY created_at DESC
    LIMIT :limit_val OFFSET :offset_val
"""

JOBS_COUNT_QUERY = """
    SELECT COUNT(*) FROM job_runs WHERE 1=1
      {status_filter}
      {type_filter}
"""

JOBS_STATS_QUERY = """
    SELECT
        COUNT(*) AS total,
        COUNT(CASE WHEN status = 'success' THEN 1 END) AS success,
        COUNT(CASE WHEN status = 'failed' THEN 1 END) AS failed,
        COUNT(CASE WHEN status = 'running' THEN 1 END) AS running,
        COUNT(CASE WHEN status = 'pending' THEN 1 END) AS pending
    FROM job_runs
    WHERE created_at >= NOW() - INTERVAL '7 days'
"""

JOBS_TYPES_QUERY = """
    SELECT DISTINCT job_type FROM job_runs ORDER BY job_type
"""


def _row_to_dict(row: tuple) -> dict[str, Any]:
    row[9]
    return {
        "id": safe_row_str(row, idx=0),
        "job_type": safe_row_str(row, idx=1),
        "status": row[2] or "unknown",
        "progress_pct": row[3] or 0,
        "started_at": row[4].isoformat() if row[4] else None,
        "completed_at": row[5].isoformat() if row[5] else None,
        "duration_seconds": row[6] or 0,
        "error_message": row[7][:300] if row[7] else None,
        "triggered_by": safe_row_str(row, idx=8),
        "created_at": row[9].isoformat() if row[9] else None,
    }


@router.get("", summary="Jobs list", description="List background jobs with filters, pagination, and stats")
async def list_jobs(
    status: str | None = Query(None, description="Filter by status: pending, running, success, failed"),
    job_type: str | None = Query(None, description="Filter by job type (exact match)"),
    limit: int = Query(50, ge=1, le=200, description="Page size"),
    offset: int = Query(0, ge=0, description="Offset for pagination"),
    session: AsyncSession = Depends(get_session),
) -> ApiResponse[dict[str, Any]]:
    try:
        list_params: dict[str, Any] = {"limit_val": limit, "offset_val": offset}
        count_params: dict[str, Any] = {}

        status_filter = ""
        if status:
            status_filter = "AND status = :status_val"
            list_params["status_val"] = status
            count_params["status_val"] = status

        type_filter = ""
        if job_type:
            type_filter = "AND job_type = :job_type_val"
            list_params["job_type_val"] = job_type
            count_params["job_type_val"] = job_type

        # Fetch counts
        count_sql = JOBS_COUNT_QUERY.format(status_filter=status_filter, type_filter=type_filter)
        r = await session.execute(text(count_sql), count_params)
        total = r.scalar() or 0

        # Fetch rows
        list_sql = JOBS_LIST_QUERY.format(status_filter=status_filter, type_filter=type_filter)
        r = await session.execute(text(list_sql), list_params)
        items = [_row_to_dict(row) for row in r.fetchall()]

        # Fetch stats (7-day rollup, no filter)
        stats = {"total": 0, "success": 0, "failed": 0, "running": 0, "pending": 0}
        try:
            r = await session.execute(text(JOBS_STATS_QUERY))
            row = r.fetchone()
            if row:
                stats = {
                    "total": row[0] or 0,
                    "success": row[1] or 0,
                    "failed": row[2] or 0,
                    "running": row[3] or 0,
                    "pending": row[4] or 0,
                }
        except Exception:
            logger.warning("Failed to fetch job stats", exc_info=True)

        # Fetch distinct job types
        job_types: list[str] = []
        try:
            r = await session.execute(text(JOBS_TYPES_QUERY))
            job_types = [row[0] for row in r.fetchall()]
        except Exception:
            pass

        return ApiResponse[dict[str, Any]](success=True, data={
            "items": items,
            "total": total,
            "limit": limit,
            "offset": offset,
            "stats": stats,
            "job_types": job_types,
        })
    except Exception:
        logger.exception("Failed to fetch jobs")
        return ApiResponse[dict[str, Any]](
            success=True,
            data={"items": [], "total": 0, "limit": limit, "offset": offset, "stats": {}, "job_types": []},
        )


# ──────────────────────────────────────────────
#  Distributed Job Queue Monitoring
#  (Redis-backed worker queue — JobQueueConsumer)
# ──────────────────────────────────────────────


async def _queue_len(client: Any, key: str) -> int:
    """Live length of a Redis list; 0 when Redis is unavailable."""
    if client is None:
        return 0
    try:
        return int(await client.llen(key)) or 0
    except Exception:
        return 0


@router.get(
    "/queue/stats",
    summary="Job queue stats",
    description="Consumer diagnostics + live Redis queue sizes (main queue, "
    "dead-letter) for the distributed job queue. Admin only.",
)
async def job_queue_stats() -> ApiResponse[dict[str, Any]]:
    """Expose ``JobQueueConsumer.stats()`` plus live queue lengths.

    The ``/jobs`` router is admin-protected, so this is a management
    endpoint. When the queue is disabled (``JOB_QUEUE_ENABLED=false``) the
    consumer singleton still exists but reports ``running=false``; the Redis
    list lengths reflect the actual stored messages either way.
    """
    try:
        from jobs.queue_consumer import get_job_queue_consumer

        consumer = get_job_queue_consumer()
        stats = consumer.stats()

        # Live queue sizes from Redis (async LLEN)
        client = consumer._redis()
        queue_size = await _queue_len(client, settings.job_queue_name)
        dead_letter_size = await _queue_len(client, settings.job_queue_dead_letter)

        return ApiResponse[dict[str, Any]](success=True, data={
            **stats,
            "queue_size": queue_size,
            "dead_letter_size": dead_letter_size,
            "queue_enabled": settings.job_queue_enabled,
            "config": {
                "queue": settings.job_queue_name,
                "dead_letter": settings.job_queue_dead_letter,
                "max_retries": consumer._max_retries,
                "poll_timeout_s": consumer._poll_timeout,
                "auth_enabled": bool(consumer._token),
            },
        })
    except Exception as exc:
        logger.exception("Failed to read job queue stats")
        return ApiResponse(success=False, error={"message": str(exc)}, data={})


async def _get_queue_redis() -> Any | None:
    """Shared Redis client for queue operations (None when unavailable)."""
    try:
        from core.cache import get_cache

        cache = get_cache()
        await cache.initialize()
        return cache.client
    except Exception:
        logger.warning("Redis unavailable for queue replay", exc_info=True)
        return None


_REPLAY_MODES = {"replay", "discard", "list", "dry-run"}


_SUMMARY_WINDOWS = ("all", "today", "week", "24h")


@router.get(
    "/queue/summary",
    summary="Dead-letter queue summary",
    description="Aggregate report of job:dead messages — job_name distribution, "
    "error categories, top errors, and repeated job_ids. Optional time-window "
    "filter (today | week | 24h | all) based on dead_lettered_at. Admin only. Read-only.",
)
async def dead_letter_summary(
    window: str = Query("all", description="Time window: all | today | week | 24h"),
    since: float | None = Query(None, ge=0, description="Explicit epoch-seconds threshold (overrides window)"),
) -> ApiResponse[dict[str, Any]]:
    """Return an aggregated troubleshooting report of the dead-letter queue.

    Pure read: distribution of ``job_name``s, coarse error categories,
    top raw error strings, and repeated ``job_id``s (the same logical
    message dead-lettered multiple times). Helps answer "what keeps
    failing?" without dumping every message.

    ``window`` restricts the report to messages dead-lettered in the last
    day / this week / today (Tehran) via ``dead_lettered_at``; an explicit
    ``since`` epoch threshold overrides it. The applied window and
    threshold are echoed back so clients can display what was filtered.
    """
    try:
        from jobs.replay import summarize_dead_letter

        if window not in _SUMMARY_WINDOWS:
            return ApiResponse(
                success=False,
                error={"message": f"Invalid window '{window}' — must be one of {_SUMMARY_WINDOWS}"},
                data={},
            )

        redis = await _get_queue_redis()
        if redis is None:
            return ApiResponse(success=False, error={"message": "Redis unavailable"}, data={})

        summary = await summarize_dead_letter(
            redis,
            dead_queue=settings.job_queue_dead_letter,
            window=window,
            since=since,
        )

        return ApiResponse[dict[str, Any]](success=True, data={
            "total": summary.total,
            "queue": summary.queue,
            "window": summary.window,
            "since": summary.since,
            "job_names": summary.job_names,
            "error_categories": summary.error_categories,
            "top_errors": summary.top_errors,
            "repeated": summary.repeated,
            "repeated_messages": summary.repeated_messages,
            "malformed": summary.malformed,
        })
    except Exception as exc:
        logger.exception("Failed to summarize dead-letter queue")
        return ApiResponse(success=False, error={"message": str(exc)}, data={})


@router.post(
    "/queue/replay",
    summary="Replay dead-letter jobs",
    description="Replay (or discard / list / dry-run) dead-letter job messages back "
    "to the main queue — same logic as scripts/replay_dead_letter.py, without "
    "the CLI. Admin only.",
)
async def replay_job_queue(
    job_name: str | None = Query(None, description="Only process jobs with this exact name"),
    search: str | None = Query(None, description="Substring search across the serialised payload"),
    limit: int = Query(0, ge=0, le=10000, description="Max messages to process (0 = all)"),
    mode: str = Query("replay", description="replay | discard | list | dry-run"),
) -> ApiResponse[dict[str, Any]]:
    """Replay dead-letter jobs from the admin panel (no CLI needed).

    Delegates to the shared ``jobs.replay.replay_dead_letter_messages``
    core so the CLI script and this endpoint always behave identically:
    fresh ``attempt`` budget, current worker token, remove from dead only
    after a successful push (no data loss).
    """
    if mode not in _REPLAY_MODES:
        return ApiResponse(
            success=False,
            error={"message": f"Invalid mode '{mode}' — must be one of {sorted(_REPLAY_MODES)}"},
            data={},
        )

    try:
        from jobs.replay import current_token, replay_dead_letter_messages

        redis = await _get_queue_redis()
        if redis is None:
            return ApiResponse(success=False, error={"message": "Redis unavailable"}, data={})

        result = await replay_dead_letter_messages(
            redis,
            queue_name=settings.job_queue_name,
            dead_queue=settings.job_queue_dead_letter,
            token=current_token(settings.job_queue_token),
            job_name=job_name,
            search=search,
            limit=limit,
            mode=mode,
        )

        return ApiResponse[dict[str, Any]](success=True, data={
            "mode": result.mode,
            "total": result.total,
            "replayed": result.replayed,
            "failed": result.failed,
            "discarded": result.discarded,
            "queue": result.queue,
            "dead_queue": result.dead_queue,
            "queue_size": result.queue_size,
            "dead_size": result.dead_size,
            "messages": [
                {
                    "job_name": m.job_name,
                    "job_id": m.job_id,
                    "attempt": m.attempt,
                    "error": m.error,
                    "status": m.status,
                    "message": m.message,
                }
                for m in result.messages
            ],
        })
    except Exception as exc:
        logger.exception("Failed to replay dead-letter queue")
        return ApiResponse(success=False, error={"message": str(exc)}, data={})
