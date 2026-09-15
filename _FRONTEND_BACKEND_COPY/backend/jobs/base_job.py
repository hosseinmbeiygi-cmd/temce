from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import UTC, datetime

from core.logging import get_logger
from jobs.job_context import JobContext
from jobs.job_result import JobResult

logger = get_logger(__name__)


class BaseJob(ABC):
    def __init__(self, name: str = ""):
        self._name = name or self.__class__.__name__
        self._started_at: datetime | None = None
        self._completed_at: datetime | None = None

    @abstractmethod
    async def execute(self, context: JobContext) -> JobResult: ...

    @property
    def name(self) -> str:
        return self._name

    @property
    def started_at(self) -> datetime | None:
        return self._started_at

    @property
    def completed_at(self) -> datetime | None:
        return self._completed_at

    async def run(self, context: JobContext) -> JobResult:
        self._started_at = datetime.now(UTC)
        logger.info("Job %s started", self._name)
        try:
            result = await self.execute(context)
            self._completed_at = datetime.now(UTC)
            duration = (self._completed_at - self._started_at).total_seconds()
            logger.info("Job %s completed in %.2fs (success=%s)", self._name, duration, result.success)
            return result
        except Exception as e:
            self._completed_at = datetime.now(UTC)
            logger.error("Job %s failed: %s", self._name, e)
            return JobResult.failure(str(e), job_name=self._name)
