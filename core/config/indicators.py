from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict


class IndicatorSettings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="INDICATOR_", env_file=".env", extra="ignore")

    default_period: int = 14
    ema_span: int = 12
    sma_span: int = 20
    bollinger_period: int = 20
    bollinger_std: float = 2.0
    rsi_period: int = 14
    macd_fast: int = 12
    macd_slow: int = 26
    macd_signal: int = 9
    atr_period: int = 14
    volume_ma_period: int = 20
    cache_results: bool = True
    cache_ttl_seconds: int = 3600
