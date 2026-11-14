from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict

from core.config import _ENV_FILE


class StorageSettings(BaseSettings):
    # Same repository-anchored .env as core.config.Settings, so the values do
    # not change with the process working directory (CFG-06).
    model_config = SettingsConfigDict(env_prefix="STORAGE_", env_file=str(_ENV_FILE), extra="ignore")

    backend: str = "local"
    local_path: str = "./data/storage"
    s3_bucket: str | None = None
    s3_region: str = "us-east-1"
    s3_access_key: str | None = None
    s3_secret_key: str | None = None
    s3_endpoint_url: str | None = None
    gcs_bucket: str | None = None
    azure_container: str | None = None
    max_file_size_mb: int = 100
    compression_enabled: bool = True
    encryption_enabled: bool = False
    retention_days: int = 90
    archive_after_days: int = 30
