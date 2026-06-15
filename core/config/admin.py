from __future__ import annotations

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class AdminSettings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="ADMIN_", env_file=".env", extra="ignore")

    enabled: bool = True
    secret_key: str = Field(default="admin-secret", alias="ADMIN_SECRET_KEY")
    session_timeout_minutes: int = 30
    max_login_attempts: int = 5
    allowed_ips: list[str] = ["127.0.0.1"]
    dashboard_url: str = "/admin"
    audit_log_enabled: bool = True
    metrics_refresh_seconds: int = 10
