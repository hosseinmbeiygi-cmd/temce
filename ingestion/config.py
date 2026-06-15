from __future__ import annotations

from enum import StrEnum
from typing import Any

from pydantic import Field, PostgresDsn, field_validator
from pydantic_settings import BaseSettings


class SourceType(StrEnum):
    TSETMC_MARKETWATCH = "tsetmc_marketwatch"
    TSETMC_TRADES = "tsetmc_trades"
    TSETMC_ORDERBOOK = "tsetmc_orderbook"
    IFB = "ifb"
    IME = "ime"
    DERIVATIVES = "derivatives"
    CODAL = "codal"


class StorageType(StrEnum):
    POSTGRES = "postgres"
    TIMESCALEDB = "timescaledb"


class IngestionConfig(BaseSettings):
    model_config = {"env_prefix": "INGESTION_", "env_file": ".env", "extra": "ignore"}

    enabled_sources: list[SourceType] = Field(
        default=list(SourceType),
        description="Active data sources",
    )

    worker_count: int = Field(default=4, ge=1, le=32)
    max_retries: int = Field(default=3, ge=0)
    retry_backoff_base: float = Field(default=2.0, ge=1.0)
    retry_max_delay: float = Field(default=60.0, ge=1.0)

    request_timeout: float = Field(default=30.0, ge=1.0)
    connection_pool_size: int = Field(default=20, ge=1)
    rate_limit_calls: int = Field(default=10, ge=1)
    rate_limit_period: int = Field(default=1, ge=1)

    lake_bucket_raw: str = Field(default="raw-payloads")
    lake_bucket_parsed: str = Field(default="parsed-data")
    lake_endpoint: str = Field(default="http://minio:9000")
    lake_access_key: str = Field(default="minioadmin")
    lake_secret_key: str = Field(default="minioadmin")
    lake_region: str = Field(default="us-east-1")

    db_dsn: PostgresDsn = Field(
        default=PostgresDsn("postgresql+asyncpg://postgres:postgres@localhost:5432/marketdb"),
    )
    db_pool_size: int = Field(default=10, ge=1)
    db_max_overflow: int = Field(default=20, ge=0)

    redis_url: str = Field(default="redis://localhost:6379/0")

    scheduler_interval_seconds: int = Field(default=15, ge=1, le=3600)
    market_open: str = Field(default="08:30")
    market_close: str = Field(default="15:30")
    market_timezone: str = Field(default="Asia/Tehran")

    dedup_window_minutes: int = Field(default=60, ge=1)

    replay_chunk_size: int = Field(default=1000, ge=1)
    replay_concurrency: int = Field(default=2, ge=1)

    @field_validator("db_dsn", mode="before")
    @classmethod
    def coerce_dsn(cls, v: Any) -> str:
        return str(v)

    @property
    def market_hours_enabled(self) -> bool:
        return bool(self.market_open and self.market_close)
