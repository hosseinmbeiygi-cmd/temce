from __future__ import annotations

from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class PathSettings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="PATH_", env_file=".env", extra="ignore")

    data_dir: str = "./data"
    log_dir: str = "./logs"
    config_dir: str = "./config"
    temp_dir: str = "./tmp"
    model_dir: str = "./data/models"
    export_dir: str = "./data/exports"
    archive_dir: str = "./data/archive"
    backup_dir: str = "./data/backup"
    migration_dir: str = "./migrations"

    def ensure_dirs(self) -> None:
        for attr in (
            "data_dir",
            "log_dir",
            "config_dir",
            "temp_dir",
            "model_dir",
            "export_dir",
            "archive_dir",
            "backup_dir",
        ):
            path = Path(getattr(self, attr))
            path.mkdir(parents=True, exist_ok=True)
