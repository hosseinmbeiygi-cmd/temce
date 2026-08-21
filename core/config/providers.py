from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict


class ProviderSettings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="PROVIDER_", env_file=".env", extra="ignore")

    default_timeout: int = 30
    max_retries: int = 3
    rate_limit_per_minute: int = 60
    rate_limit_burst: int = 10
    enable_failover: bool = True
    enable_circuit_breaker: bool = True
    circuit_breaker_failure_threshold: int = 5
    circuit_breaker_recovery_timeout: float = 30.0
    health_check_interval_seconds: int = 60
    concurrent_requests: int = 10
    tsetmc_base_url: str = "https://tsetmc.com"
    tsetmc_ws_url: str | None = None
    codal_base_url: str = "https://codal.ir"
