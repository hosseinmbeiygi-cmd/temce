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

    database_url: str = Field(default="postgresql+asyncpg://market:market@localhost:5432/market", alias="DATABASE_URL")
    database_pool_size: int = 20
    database_max_overflow: int = 30
    database_echo: bool = False

    redis_url: str = Field(default="redis://localhost:6379/0", alias="REDIS_URL")
    redis_default_ttl: int = 300

    log_level: str = "INFO"
    log_format: str = "json"
    log_file: str | None = None

    api_prefix: str = "/api/v1"
    api_title: str = "Iran Market Platform API"
    api_version: str = "0.1.0"
    # Safe-by-default: restricted to the documented local dev origin.
    # Set CORS_ORIGINS explicitly for other origins (e.g. ["https://yourdomain.com"]).
    cors_origins: list[str] = Field(default=["http://localhost:3000"], alias="CORS_ORIGINS")

    secret_key: str = Field(default="change-me-in-production", alias="SECRET_KEY")
    access_token_expire_minutes: int = 60
    refresh_token_expire_days: int = 30
    jwt_algorithm: str = "HS256"
    bcrypt_rounds: int = 12
    max_login_attempts: int = 5
    lockout_minutes: int = 15
    session_timeout_minutes: int = 30
    enable_csrf: bool = True
    api_key_header: str = "X-API-Key"

    # Only auto-create tables when explicitly enabled (dev mode without running
    # alembic). Production must use Alembic migrations — never create_all.
    database_auto_create_tables: bool = False

    data_dir: str = str(Path.cwd() / "data")
    storage_backend: str = "local"
    s3_bucket: str | None = None

    provider_default_timeout: int = 30
    provider_max_retries: int = 3
    provider_rate_limit_per_minute: int = 300  # Personal system: generous default

    # Per-endpoint rate limits: {"path_pattern": "max_requests_per_minute"}
    # These override the default provider_rate_limit_per_minute for specific endpoints.
    # Example: {"/api/v1/signals": 10, "/api/v1/backtests/run": 5, "/api/v1/ml/train": 2}
    endpoint_rate_limits: dict[str, int] = Field(
        default_factory=lambda: {
            # ── Signals & Recommendations ──
            "/api/v1/signals": 10,
            "/api/v1/signal-insights": 10,
            "/api/v1/signal-insights/generate": 5,

            # ── Backtesting (expensive) ──
            "/api/v1/backtests/run": 5,
            "/api/v1/backtests/generate": 5,
            "/api/v1/backtests/cascade": 2,
            "/api/v1/backtests/adaptive": 2,

            # ── ML (expensive) ──
            "/api/v1/ml/train": 2,
            "/api/v1/ml/predict": 20,
            "/api/v1/ml/evaluate": 5,

            # ── Portfolios & Alerts ──
            "/api/v1/portfolios": 30,
            "/api/v1/alerts": 30,
            "/api/v1/watchlist": 60,

            # ── Screener ──
            "/api/v1/screener-v2": 20,
            "/api/v1/screener-v2/run": 5,
            "/api/v1/screener110": 20,

            # ── Chat & Assistant ──
            "/api/v1/chat": 20,
            "/api/v1/stock-assistant": 15,
            "/api/v1/assistant": 15,
            "/api/v1/compose": 10,

            # ── Data Import (expensive) ──
            "/api/v1/data-import": 5,
            "/api/v1/data-import/sync": 2,

            # ── Auth (strict) ──
            "/api/v1/auth/login": 10,
            "/api/v1/auth/register": 5,
            "/api/v1/auth/change-password": 5,
            "/api/v1/auth/refresh": 30,

            # ── Read-only (generous) ──
            "/api/v1/heatmap": 60,
            "/api/v1/news": 60,
            "/api/v1/codal": 30,
            "/api/v1/economic-calendar": 30,
            "/api/v1/macro": 30,
            "/api/v1/decision-engine": 30,
            "/api/v1/recommendations": 30,
            "/api/v1/funds": 30,
            "/api/v1/bourse": 30,
            "/api/v1/futures": 30,
            "/api/v1/commodity": 30,
            "/api/v1/crypto": 30,
        },
        description="Per-endpoint rate limits (requests per minute)",
    )

    # Rate limit response headers
    rate_limit_include_headers: bool = True  # Add X-RateLimit-* headers to responses

    tsetmc_base_url: str = "http://tsetmc.com"

    tsetmc_api_key: str = ""
    tsetmc_ws_url: str | None = None
    codal_base_url: str = "https://codal.ir"
    codal_api_key: str = ""
    codal_excel_dir: str = Field(default="", alias="CODAL_EXCEL_DIR")
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
    metrics_path: str = "/metrics"
    otlp_endpoint: str | None = None
    sentry_dsn: str | None = None

    # Centralized log aggregation (Redis Streams). Enable in multi-service
    # deployments where a collector (Loki/Vector) tails the stream.
    log_aggregation_enabled: bool = False
    log_aggregation_source: str = "api"

    jobs_max_concurrent: int = 4
    jobs_default_timeout_minutes: int = 30
    scheduler_timezone: str = "Asia/Tehran"

    # Telegram notifications (optional)
    telegram_bot_token: str = ""
    telegram_chat_id: str = ""

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
        if "postgres" in self.database_url:
            # Already has a driver suffix like +asyncpg or +psycopg2
            if "+" in self.database_url.split("://", 1)[0]:
                return self.database_url
            return self.database_url.replace("://", "+asyncpg://", 1)
        return self.database_url

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
