from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from core.database import get_session
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
    created = row[9]
    return {
        "id": row[0] or "",
        "job_type": row[1] or "",
        "status": row[2] or "unknown",
        "progress_pct": row[3] or 0,
        "started_at": row[4].isoformat() if row[4] else None,
        "completed_at": row[5].isoformat() if row[5] else None,
        "duration_seconds": row[6] or 0,
        "error_message": row[7][:300] if row[7] else None,
        "triggered_by": row[8] or "",
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
