from __future__ import annotations

from core.exceptions import AppError


class SchedulerError(AppError):
    def __init__(self, message: str = "Scheduler error", code: str = "SCHEDULER_ERROR") -> None:
        super().__init__(message=message, code=code)


class JobNotFoundError(SchedulerError):
    def __init__(self, job_id: str = "") -> None:
        super().__init__(message=f"Job not found: {job_id}", code="JOB_NOT_FOUND")


class JobExecutionError(SchedulerError):
    def __init__(self, job_id: str = "", message: str = "Job execution failed") -> None:
        super().__init__(message=f"{message}: {job_id}" if job_id else message, code="JOB_EXECUTION_ERROR")


class JobTimeoutError(SchedulerError):
    def __init__(self, job_id: str = "", timeout: int = 0) -> None:
        super().__init__(message=f"Job {job_id} timed out after {timeout}s", code="JOB_TIMEOUT")


class ScheduleConflictError(SchedulerError):
    def __init__(self, message: str = "Schedule conflict") -> None:
        super().__init__(message=message, code="SCHEDULE_CONFLICT")
