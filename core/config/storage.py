from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict


class StorageSettings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="STORAGE_", env_file=".env", extra="ignore")

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
