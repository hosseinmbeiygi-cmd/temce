"""Best-effort persistence of job lifecycle metadata into ``job_runs``.

The admin console derives every pipeline card's status from this table.
Before this module existed nothing ever wrote to ``job_runs``, so all cards
rendered "نامشخص" even while the scheduler was executing jobs normally.

Recording must never break a job: every database failure is swallowed and
logged.  A separate short-lived session is used so the recorder cannot
interfere with the transaction a job owns.
"""

from __future__ import annotations

import json
import time
from datetime import datetime
from typing import Any

import core.database as database
from core.logging import get_logger
from jobs.job_result import JobResult
from models.job_run import JobRunModel

logger = get_logger(__name__)


async def _new_session():
    """Open a fresh primary-DB session (initialising the engine if needed)."""
    if database.async_session_factory is None:
        await database.init_database()
    assert database.async_session_factory is not None
    return database.async_session_factory()


class JobRunRecorder:
    """Write start/finish rows to ``job_runs`` without affecting job execution."""

    async def start(self, job_name: str, params: dict[str, Any] | None, job_id: str) -> float:
        """Insert a ``running`` row; return a monotonic timestamp for duration."""
        monotonic = time.monotonic()
        try:
            async with await _new_session() as session:
                session.add(
                    JobRunModel(
                        id=job_id[:50],
                        job_type=job_name[:100],
                        status="running",
                        started_at=datetime.now(),
                        progress_pct=0,
                        params=json.dumps(params or {}, ensure_ascii=False, default=str)[:8000],
                        triggered_by="scheduler",
                    )
                )
                await session.commit()
        except Exception:
            logger.warning("Could not record job start for %s", job_name, exc_info=True)
        return monotonic

    async def finish(
        self,
        job_id: str,
        job_name: str,
        monotonic: float,
        result: JobResult | None,
        error: str | None = None,
    ) -> None:
        """Finalise the row with status, duration and error/result payload."""
        if result is None:
            status = "failed"
            message = error or "unknown error"
            data: dict[str, Any] = {}
        elif result.skipped:
            # "skipped" is a valid gate outcome, not a failure (see JobResult).
            status = "skipped"
            message = result.message
            data = result.data
        elif result.success:
            status = "success"
            message = result.message
            data = result.data
        else:
            status = "failed"
            message = result.error or result.message
            data = result.data

        payload = json.dumps(data, ensure_ascii=False, default=str)[:8000]
        try:
            async with await _new_session() as session:
                row = await session.get(JobRunModel, job_id[:50])
                if row is None:
                    # Start record failed (e.g. brief DB outage) — write a
                    # complete row now rather than losing the run entirely.
                    now = datetime.now()
                    session.add(
                        JobRunModel(
                            id=job_id[:50],
                            job_type=job_name[:100],
                            status=status,
                            started_at=now,
                            completed_at=now,
                            duration_seconds=round(time.monotonic() - monotonic, 3),
                            error_message=(message or "")[:2000] or None,
                            result=payload or None,
                            triggered_by="scheduler",
                        )
                    )
                else:
                    row.status = status
                    row.completed_at = datetime.now()
                    row.duration_seconds = round(time.monotonic() - monotonic, 3)
                    row.error_message = (message or "")[:2000] or None
                    row.result = payload or None
                    if status in ("success", "skipped"):
                        row.progress_pct = 100
                await session.commit()
        except Exception:
            logger.warning("Could not record job finish for %s", job_name, exc_info=True)


job_run_recorder = JobRunRecorder()
