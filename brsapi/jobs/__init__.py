"""
BrsApi Scheduled Jobs
=====================

APScheduler / Celery Beat job definitions for periodic data sync.
Each job targets a specific BrsApi endpoint with the appropriate
sync interval.
"""

from brsapi.jobs.registry import (
    BrsApiJobRegistry,
    BrsApiSyncJob,
    register_all_brsapi_jobs,
)

__all__ = [
    "BrsApiJobRegistry",
    "BrsApiSyncJob",
    "register_all_brsapi_jobs",
]
