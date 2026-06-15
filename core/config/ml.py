from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict


class MLSettings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="ML_", env_file=".env", extra="ignore")

    model_dir: str = "./data/models"
    default_batch_size: int = 2048
    device: str = "cpu"
    random_seed: int = 42
    experiment_tracker_uri: str | None = None
    feature_store_uri: str | None = None
    registry_uri: str | None = None
    training_timeout_minutes: int = 120
    inference_timeout_seconds: int = 30
    max_model_size_mb: int = 500
    enable_auto_ml: bool = False
    enable_explainability: bool = True
    enable_drift_detection: bool = True
    drift_alert_threshold: float = 0.15
