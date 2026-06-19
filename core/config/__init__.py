from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    app_name: str = "iran-market-platform"
    debug: bool = False
    environment: str = Field(default="development", alias="ENV")

    server_host: str = "0.0.0.0"
    server_port: int = 8000
    workers: int = 1

    database_url: str = Field(default="sqlite:///data/market.db", alias="DATABASE_URL")
    database_pool_size: int = 5
    database_max_overflow: int = 10
    database_echo: bool = False

    redis_url: str = Field(default="redis://localhost:6379/0", alias="REDIS_URL")
    redis_default_ttl: int = 300

    log_level: str = "INFO"
    log_format: str = "json"
    log_file: str | None = None

    api_prefix: str = "/api/v1"
    api_title: str = "Iran Market Platform API"
    api_version: str = "0.1.0"
    cors_origins: list[str] = ["*"]  # Override in production: ["https://yourdomain.com"]

    secret_key: str = Field(default="change-me-in-production", alias="SECRET_KEY")
    access_token_expire_minutes: int = 60
    api_key_header: str = "X-API-Key"

    data_dir: str = str(Path.cwd() / "data")
    storage_backend: str = "local"
    s3_bucket: str | None = None

    provider_default_timeout: int = 30
    provider_max_retries: int = 3
    provider_rate_limit_per_minute: int = 60

    tsetmc_base_url: str = "http://tsetmc.com"
    tsetmc_api_key: str = ""
    tsetmc_ws_url: str | None = None
    codal_base_url: str = "https://codal.ir"
    codal_api_key: str = ""
    fipiran_api_key: str = ""

    ml_model_dir: str = str(Path.cwd() / "data" / "models")
    ml_default_batch_size: int = 2048
    ml_device: str = "cpu"
    ml_random_seed: int = 42
    ml_experiment_tracker_uri: str | None = None

    backtest_default_capital: float = 1_000_000_000
    backtest_default_commission_pct: float = 0.0035
    backtest_default_slippage_bps: float = 10.0

    monitoring_enabled: bool = True
    otlp_endpoint: str | None = None
    sentry_dsn: str | None = None

    jobs_max_concurrent: int = 4
    jobs_default_timeout_minutes: int = 30
    scheduler_timezone: str = "Asia/Tehran"

    @property
    def is_production(self) -> bool:
        return self.environment == "production"

    @property
    def is_development(self) -> bool:
        return self.environment == "development"

    def validate_production(self) -> None:
        if not self.is_production:
            return
        errors: list[str] = []
        if self.secret_key == "change-me-in-production":
            errors.append("SECRET_KEY must be changed from default in production")
        if self.cors_origins == ["*"]:
            errors.append("CORS_ORIGINS must be restricted in production")
        if self.database_url.startswith("sqlite"):
            errors.append("SQLite cannot be used in production")
        if self.otlp_endpoint is None:
            errors.append("OTLP_ENDPOINT should be configured for observability in production")
        if errors:
            raise RuntimeError("Production config validation failed:\n" + "\n".join(f"  - {e}" for e in errors))

    @property
    def database_url_async(self) -> str:
        if self.database_url.startswith("sqlite"):
            return self.database_url.replace("sqlite:///", "sqlite+aiosqlite:///")
        return (
            self.database_url.replace("://", "+asyncpg://", 1) if "postgres" in self.database_url else self.database_url
        )

    @property
    def data_path(self) -> Path:
        p = Path(self.data_dir)
        p.mkdir(parents=True, exist_ok=True)
        return p

    @property
    def ml_model_path(self) -> Path:
        p = Path(self.ml_model_dir)
        p.mkdir(parents=True, exist_ok=True)
        return p


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
