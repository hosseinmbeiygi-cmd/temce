from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict


class FeatureFlagSettings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="FF_", env_file=".env", extra="ignore")

    use_ml_models: bool = True
    use_websocket: bool = True
    use_cache: bool = True
    use_advanced_backtest: bool = False
    enable_audit: bool = True
    enable_sentry: bool = False
    enable_metrics: bool = True
    enable_provider_failover: bool = True
    enable_auto_retry: bool = True
    enable_rate_limiting: bool = True
    enable_circuit_breaker: bool = True
