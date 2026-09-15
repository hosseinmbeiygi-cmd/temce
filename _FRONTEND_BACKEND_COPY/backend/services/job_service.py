from __future__ import annotations

from typing import Any

from core.logging import get_logger
from core.result import Result

logger = get_logger(__name__)


class JobService:
    async def list_jobs(self) -> Result[list[dict[str, Any]]]:
        return Result.ok([])

    async def get_job_status(self, job_name: str) -> Result[dict[str, Any]]:
        return Result.fail(f"Job {job_name} not found")

    async def run_job(self, job_name: str, params: dict[str, Any] | None = None) -> Result[dict[str, Any]]:
        return Result.ok({"job": job_name, "status": "started"})

    async def get_history(self, job_name: str, limit: int = 20) -> Result[list[dict[str, Any]]]:
        return Result.ok([])
