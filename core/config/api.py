from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict


class ApiSettings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="API_", env_file=".env", extra="ignore")

    host: str = "0.0.0.0"
    port: int = 8000
    workers: int = 1
    prefix: str = "/api/v1"
    title: str = "Iran Market Platform API"
    version: str = "0.1.0"
    cors_origins: list[str] = ["*"]
    cors_allow_credentials: bool = True
    cors_allow_methods: list[str] = ["*"]
    cors_allow_headers: list[str] = ["*"]
    rate_limit_per_minute: int = 60
    max_request_size_mb: int = 10
    request_timeout_seconds: int = 30
    docs_enabled: bool = True
    debug: bool = False
