"""Currency-service specific settings. Extends (does not replace) core.config."""

from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict

from core.config import _ENV_FILE


class CurrencyServiceSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="CURRENCY_",
        # Repository-anchored, not CWD-relative (CFG-06).
        env_file=str(_ENV_FILE),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    api_prefix: str = "/api/v1"
    port: int = 8002
    jitter_pct: float = 0.3
    enable_alerts: bool = False  # Telegram real dispatch
    cache_ttl_seconds: int = 10
    use_live: bool = False  # CURRENCY_USE_LIVE=true → Tgju/Nobitex (per-venue fixture fallback)


settings = CurrencyServiceSettings()
