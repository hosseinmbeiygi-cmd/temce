from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict


class MonitoringSettings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="MONITORING_", env_file=".env", extra="ignore")

    enabled: bool = True
    otlp_endpoint: str | None = None
    sentry_dsn: str | None = None
    metrics_port: int = 9090
    metrics_path: str = "/metrics"
    health_check_path: str = "/health"
    liveness_path: str = "/live"
    readiness_path: str = "/ready"
    collect_interval_seconds: int = 15
    export_interval_seconds: int = 60
    enable_process_metrics: bool = True
    enable_gc_metrics: bool = True
