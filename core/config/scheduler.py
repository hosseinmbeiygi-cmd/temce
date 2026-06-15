from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict


class SchedulerSettings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="SCHEDULER_", env_file=".env", extra="ignore")

    enabled: bool = True
    timezone: str = "Asia/Tehran"
    max_concurrent_jobs: int = 4
    default_timeout_minutes: int = 30
    heartbeat_interval_seconds: int = 30
    poll_interval_seconds: int = 10
    missed_job_grace_minutes: int = 5
    retry_delay_seconds: int = 60
    max_retries: int = 3
    store_results: bool = True
    result_ttl_hours: int = 168
