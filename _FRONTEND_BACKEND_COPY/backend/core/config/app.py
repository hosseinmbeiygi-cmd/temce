from __future__ import annotations

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class AppSettings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="APP_", env_file=".env", extra="ignore")

    name: str = "iran-market-platform"
    debug: bool = False
    environment: str = Field(default="development", alias="ENV")
    log_level: str = "INFO"
    log_format: str = "json"
    timezone: str = "Asia/Tehran"
    data_dir: str = "./data"
    temp_dir: str = "./tmp"
    max_workers: int = 4
    shutdown_timeout_seconds: int = 30
    version: str = "0.1.0"
