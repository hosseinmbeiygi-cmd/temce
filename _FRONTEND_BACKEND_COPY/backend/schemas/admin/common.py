from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel


class SystemStatusResponse(BaseModel):
    status: str = "healthy"
    uptime_seconds: float = 0.0
    version: str = "0.1.0"
    environment: str = "development"
    database_connected: bool = True
    redis_connected: bool = False
    active_workers: int = 0
    last_health_check: datetime | None = None


class AdminStatsResponse(BaseModel):
    total_instruments: int = 0
    total_quotes: int = 0
    total_signals: int = 0
    total_recommendations: int = 0
    total_users: int = 0
    total_backtests: int = 0
    total_ml_models: int = 0
    active_jobs: int = 0
    storage_used_mb: float = 0.0
    api_requests_today: int = 0
