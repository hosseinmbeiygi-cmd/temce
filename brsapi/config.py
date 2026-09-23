"""
BrsApi.ir Configuration
=======================

Rate limits based on official BrsApi.ir documentation:
  format: requests_per_interval / interval_seconds

Endpoint Reference: https://api.brsapi.ir
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum

from pydantic import Field
from pydantic_settings import BaseSettings


class EndpointCategory(StrEnum):
    TSETMC = "tsetmc"
    CODAL = "codal"
    IME = "ime"
    COMMODITY = "commodity"
    CRYPTOCURRENCY = "cryptocurrency"


class SyncInterval:
    REALTIME_FAST = 15
    REALTIME = 30
    REALTIME_SLOW = 60
    MODERATE = 300
    HOURLY = 3600
    DAILY = 86400
    WEEKLY = 604800


@dataclass
class EndpointConfig:
    path: str
    category: EndpointCategory
    rate_limit_per_minute: int = 30
    sync_interval_seconds: int = SyncInterval.REALTIME
    required_params: tuple[str, ...] = ("key",)
    optional_params: tuple[str, ...] = ()
    default_params: dict[str, str] = field(default_factory=dict)
    ttl_cache_seconds: int = 55
    # Critical endpoints feed the same-day market record and are re-fetched only
    # once per session, so they keep running past the soft budget ceiling.
    # Non-critical endpoints (backfills, reference lists, rebuildable snapshots)
    # are rejected once daily usage crosses ``budget_soft_reject_pct``.
    critical: bool = False


class BrsApiEndpoints:
    """
    Rate limits from BrsApi.ir official docs:
      TSETMC_AllSymbols   2/100   (2 req per 100s)
      TSETMC_Index        2/100
      TSETMC_Symbol       3/10
      TSETMC_Nav          1/10
      TSETMC_Option       3/10
      TSETMC_Transaction  2/10
      TSETMC_History      4/10
      TSETMC_Candlestick  2/10
      TSETMC_Shareholder  2/10
      CODAL_Announcement  2/10
      IME_Futures         2/10
      IME_Option          2/10
      IME_Certificate     1/10
      IME_Fund            1/10
      IME_Physical        3/10
      Market_CGCC         3/1500
      Market_GCC_Pro      0/0 (free, daily)
    """

    # ─── TSETMC ───────────────────────────────
    # AllSymbols: 2 req / 100s → ~1.2 req/min
    ALL_SYMBOLS = EndpointConfig(
        path="/Tsetmc/AllSymbols.php",
        category=EndpointCategory.TSETMC,
        rate_limit_per_minute=1,
        sync_interval_seconds=120,
        optional_params=("type",),
        default_params={"type": "1"},
        ttl_cache_seconds=60,
    )

    # Symbol: 3 req / 10s → 18 req/min
    SYMBOL_DETAIL = EndpointConfig(
        path="/Tsetmc/Symbol.php",
        category=EndpointCategory.TSETMC,
        rate_limit_per_minute=18,
        sync_interval_seconds=SyncInterval.REALTIME,
        required_params=("key", "l18"),
        ttl_cache_seconds=30,
        critical=True,
    )

    # Index: 2 req / 100s → ~1.2 req/min
    INDEX = EndpointConfig(
        path="/Tsetmc/Index.php",
        category=EndpointCategory.TSETMC,
        rate_limit_per_minute=1,
        sync_interval_seconds=120,
        required_params=("key", "type"),
        ttl_cache_seconds=60,
    )

    # Nav: 1 req / 10s → 6 req/min
    NAV = EndpointConfig(
        path="/Tsetmc/Nav.php",
        category=EndpointCategory.TSETMC,
        rate_limit_per_minute=6,
        sync_interval_seconds=SyncInterval.REALTIME_SLOW,
        required_params=("key", "l18"),
        ttl_cache_seconds=60,
        critical=True,
    )

    # Option: 3 req / 10s → 18 req/min
    OPTION = EndpointConfig(
        path="/Tsetmc/Option.php",
        category=EndpointCategory.TSETMC,
        rate_limit_per_minute=18,
        sync_interval_seconds=SyncInterval.REALTIME,
        required_params=("key",),
        ttl_cache_seconds=30,
    )

    # Transaction: 2 req / 10s → 12 req/min
    TRANSACTION = EndpointConfig(
        path="/Tsetmc/Transaction.php",
        category=EndpointCategory.TSETMC,
        rate_limit_per_minute=12,
        sync_interval_seconds=SyncInterval.REALTIME_SLOW,
        required_params=("key", "l18"),
        optional_params=("date",),
        ttl_cache_seconds=60,
        critical=True,
    )

    # History: 4 req / 10s → 24 req/min
    HISTORY_PRICE = EndpointConfig(
        path="/Tsetmc/History.php",
        category=EndpointCategory.TSETMC,
        rate_limit_per_minute=24,
        sync_interval_seconds=SyncInterval.HOURLY,
        required_params=("key", "l18"),
        default_params={"type": "0"},
        optional_params=("type",),
        ttl_cache_seconds=3600,
        critical=True,
    )

    HISTORY_REALLEGAL = EndpointConfig(
        path="/Tsetmc/History.php",
        category=EndpointCategory.TSETMC,
        rate_limit_per_minute=24,
        sync_interval_seconds=SyncInterval.HOURLY,
        required_params=("key", "l18"),
        default_params={"type": "1"},
        optional_params=("type",),
        ttl_cache_seconds=3600,
        critical=True,
    )

    # Candlestick: 2 req / 10s → 12 req/min
    CANDLESTICK = EndpointConfig(
        path="/Tsetmc/Candlestick.php",
        category=EndpointCategory.TSETMC,
        rate_limit_per_minute=12,
        sync_interval_seconds=SyncInterval.REALTIME,
        required_params=("key", "l18", "type"),
        optional_params=("count",),
        default_params={"type": "1"},
        ttl_cache_seconds=30,
        critical=True,
    )

    # Shareholder: 2 req / 10s → 12 req/min
    SHAREHOLDER = EndpointConfig(
        path="/Tsetmc/Shareholder.php",
        category=EndpointCategory.TSETMC,
        rate_limit_per_minute=12,
        sync_interval_seconds=SyncInterval.HOURLY,
        required_params=("key", "l18"),
        optional_params=("date",),
        ttl_cache_seconds=3600,
    )

    # ─── CODAL ────────────────────────────────
    # Announcement: 2 req / 10s → 12 req/min
    CODAL_ANNOUNCEMENT = EndpointConfig(
        path="/Codal/Announcement.php",
        category=EndpointCategory.CODAL,
        rate_limit_per_minute=12,
        sync_interval_seconds=SyncInterval.MODERATE,
        required_params=("key",),
        optional_params=(
            "l18", "category", "period", "audited", "unaudited",
            "only_main_company", "only_subsidiaries",
            "date_start", "date_end", "page",
        ),
        ttl_cache_seconds=240,
    )

    # ─── IME ──────────────────────────────────
    # Futures: 2 req / 10s → 12 req/min
    IME_FUTURES = EndpointConfig(
        path="/IME/Futures.php",
        category=EndpointCategory.IME,
        rate_limit_per_minute=12,
        sync_interval_seconds=SyncInterval.REALTIME,
        required_params=("key",),
        ttl_cache_seconds=30,
    )

    # IME Option: 2 req / 10s → 12 req/min
    IME_OPTION = EndpointConfig(
        path="/IME/Option.php",
        category=EndpointCategory.IME,
        rate_limit_per_minute=12,
        sync_interval_seconds=SyncInterval.REALTIME,
        required_params=("key",),
        ttl_cache_seconds=30,
    )

    # Certificate: 1 req / 10s → 6 req/min
    IME_CERTIFICATE = EndpointConfig(
        path="/IME/Certificate.php",
        category=EndpointCategory.IME,
        rate_limit_per_minute=6,
        sync_interval_seconds=SyncInterval.REALTIME_SLOW,
        required_params=("key",),
        ttl_cache_seconds=60,
    )

    # Fund: 1 req / 10s → 6 req/min
    IME_FUND = EndpointConfig(
        path="/IME/Fund.php",
        category=EndpointCategory.IME,
        rate_limit_per_minute=6,
        sync_interval_seconds=SyncInterval.REALTIME_SLOW,
        required_params=("key",),
        ttl_cache_seconds=60,
    )

    # Physical: 3 req / 10s → 18 req/min
    IME_PHYSICAL = EndpointConfig(
        path="/IME/Physical.php",
        category=EndpointCategory.IME,
        rate_limit_per_minute=18,
        sync_interval_seconds=SyncInterval.HOURLY,
        required_params=("key",),
        optional_params=("date_start", "date_end"),
        ttl_cache_seconds=3600,
    )

    # ─── COMMODITY (Market_CGCC) ─────────────
    # 3 req / 1500s → 0.12 req/min
    COMMODITY = EndpointConfig(
        path="/Market/Commodity.php",
        category=EndpointCategory.COMMODITY,
        rate_limit_per_minute=1,
        sync_interval_seconds=600,
        required_params=("key",),
        ttl_cache_seconds=600,
    )

    # ─── CRYPTOCURRENCY (Market_CGCC) ────────
    CRYPTOCURRENCY = EndpointConfig(
        path="/Market/Cryptocurrency.php",
        category=EndpointCategory.CRYPTOCURRENCY,
        rate_limit_per_minute=1,
        sync_interval_seconds=600,
        required_params=("key",),
        ttl_cache_seconds=600,
    )

    # ─── GOLD & COINS ─────────────────────────
    GOLD_COIN = EndpointConfig(
        path="/Market/Coin.php",
        category=EndpointCategory.COMMODITY,
        rate_limit_per_minute=1,
        sync_interval_seconds=600,
        required_params=("key",),
        ttl_cache_seconds=600,
    )

    GOLD_CURRENCY = EndpointConfig(
        path="/Market/Gold_Currency.php",
        category=EndpointCategory.COMMODITY,
        rate_limit_per_minute=1,
        sync_interval_seconds=600,
        required_params=("key",),
        ttl_cache_seconds=600,
    )

    GOLD_COIN_HISTORY = EndpointConfig(
        path="/Market/CoinHistory.php",
        category=EndpointCategory.COMMODITY,
        rate_limit_per_minute=1,
        sync_interval_seconds=SyncInterval.HOURLY,
        required_params=("key",),
        optional_params=("date_start", "date_end", "type"),
        ttl_cache_seconds=3600,
    )

    CURRENCY = EndpointConfig(
        path="/Market/Currency.php",
        category=EndpointCategory.COMMODITY,
        rate_limit_per_minute=1,
        sync_interval_seconds=600,
        required_params=("key",),
        ttl_cache_seconds=600,
    )

    CURRENCY_HISTORY = EndpointConfig(
        path="/Market/CurrencyHistory.php",
        category=EndpointCategory.COMMODITY,
        rate_limit_per_minute=1,
        sync_interval_seconds=SyncInterval.HOURLY,
        required_params=("key",),
        optional_params=("date_start", "date_end", "type"),
        ttl_cache_seconds=3600,
    )

    # ─── GOLD & CURRENCY PRO ─────────────────────
    # Gold_Currency_Pro (free-tier Pro): flexible endpoint with 3 modes:
    #   section=gold|currency|cryptocurrency  → real-time prices with Pro fields
    #   history=1&symbol=XYZ                  → 24h tick history
    #   history=2&symbol=XYZ&date_start=...   → daily OHLC history
    GOLD_CURRENCY_PRO = EndpointConfig(
        path="/Market/Gold_Currency_Pro.php",
        category=EndpointCategory.COMMODITY,
        rate_limit_per_minute=6,
        sync_interval_seconds=SyncInterval.REALTIME_SLOW,
        required_params=("key",),
        optional_params=("section", "history", "symbol", "date_start", "date_end"),
        ttl_cache_seconds=60,
    )

    # GOLD_24H and CURRENCY_24H removed — these endpoints return HTTP 404
    # since ~June 2026. Data is available via /Market/Gold_Currency.php.

    # ─── Lookup helpers ───────────────────────
    _ALL: dict[str, EndpointConfig] = {}

    @classmethod
    def _init_lookup(cls) -> None:
        if cls._ALL:
            return
        for attr_name in dir(cls):
            if attr_name.startswith("_"):
                continue
            val = getattr(cls, attr_name)
            if isinstance(val, EndpointConfig):
                cls._ALL[attr_name] = val

    @classmethod
    def get(cls, name: str) -> EndpointConfig | None:
        cls._init_lookup()
        return cls._ALL.get(name)

    @classmethod
    def list_by_category(cls, category: EndpointCategory) -> list[tuple[str, EndpointConfig]]:
        cls._init_lookup()
        return [(n, c) for n, c in cls._ALL.items() if c.category == category]

    @classmethod
    def all(cls) -> dict[str, EndpointConfig]:
        cls._init_lookup()
        return dict(cls._ALL)


# ──────────────────────────────────────────────
#  Settings (env-based)
# ──────────────────────────────────────────────


class BrsApiSettings(BaseSettings):
    model_config = {"env_prefix": "BRSAPI_", "env_file": ".env", "extra": "ignore"}

    api_key: str = Field(default="", description="BrsApi.ir API key")
    base_url: str = Field(default="https://api.brsapi.ir", description="BrsApi base URL")

    # Master switch — when False, the client performs NO live HTTP request
    # (returns a clear error instead). Use this while the API key is blocked
    # or over quota: the platform keeps working from the database only.
    enabled: bool = Field(
        default=True,
        description="Master switch — False = DB-only mode, no live BrsApi HTTP calls",
    )
    request_timeout: float = Field(default=30.0, ge=1.0)
    max_retries: int = Field(default=3, ge=0)
    retry_backoff_base: float = Field(default=1.5, ge=1.0)
    retry_max_delay: float = Field(default=60.0, ge=1.0)
    connection_pool_size: int = Field(default=10, ge=1)

    cache_ttl_default: int = Field(default=55, ge=1)
    cache_enabled: bool = Field(default=True)

    market_timezone: str = Field(default="Asia/Tehran")
    market_open: str = Field(default="08:30")
    market_close: str = Field(default="15:30")
    only_during_market_hours: bool = Field(default=True)

    # Per-category buckets. tsetmc was raised to 60/min to match the
    # upgraded plan (1,000 req/5min) so the candlestick backfill and the
    # other TSETMC jobs are not throttled by the category bucket.
    rate_limit_tsetmc: int = Field(default=60, ge=0)
    rate_limit_codal: int = Field(default=12, ge=0)
    rate_limit_ime: int = Field(default=12, ge=0)
    rate_limit_commodity: int = Field(default=1, ge=0)
    rate_limit_crypto: int = Field(default=1, ge=0)

    proxy_url: str | None = Field(default=None)
    # TLS certificate verification. Default True (secure). Set BRSAPI_VERIFY_SSL=false
    # only if the API endpoint presents an invalid/self-signed certificate.
    verify_ssl: bool = Field(default=True)
    health_check_interval_seconds: int = Field(default=60)
    raw_payload_sink_enabled: bool = Field(default=False)
    max_raw_payload_age_days: int = Field(default=30)

    # Global rate limits (must not be exceeded)
    # AIO (All In One) package: 500 requests per 5 minutes
    # IMPORTANT: the free/basic plan blocks the key above ~5,000 requests/day.
    # The default 4,000/day keeps a safety margin below that real-world cap so
    # the rate limiter never lets the plan get itself blocked. Set
    # BRSAPI_GLOBAL_DAILY_LIMIT in .env to your exact plan quota.
    global_daily_limit: int = Field(default=4000, ge=1, description="Max requests per day across all endpoints (hard cap — the rate limiter blocks until midnight Tehran when reached)")
    global_5min_limit: int = Field(default=1000, ge=1, description="Max requests per 5-minute window across all endpoints (upgraded plan limit)")
    # When True and the daily budget is exhausted, ``acquire()`` rejects the
    # request immediately instead of sleeping until midnight. Prevents a
    # blocked-key cascade when multiple jobs pile up past the quota.
    fail_fast_on_daily_exhausted: bool = Field(default=True)

    # Tiered budget defence (evaluated against the PERSISTED daily counter, so
    # it holds across workers and restarts). At ``budget_warn_pct`` a warning
    # is logged once per Tehran day; from ``budget_soft_reject_pct`` upward
    # only endpoints flagged ``critical`` may still spend quota, which leaves
    # head-room for the same-day market record instead of letting a backfill
    # walk the key up to the provider's block threshold.
    budget_warn_pct: int = Field(default=85, ge=1, le=100)
    budget_soft_reject_pct: int = Field(default=95, ge=1, le=100)

    # BrsApiBudgetGovernor (brsapi/budget.py) — persistent, cross-process
    # guard that prevents the key from getting blocked again. The in-process
    # RateLimiter counters reset on restart/replica, so the governor keeps the
    # REAL daily counter in Redis (INCR, atomic across workers) with a JSON
    # file fallback, and rejects every live call for a cooldown after an
    # HTTP 302 heavy-file redirect (the server's over-quota signal).
    budget_redis_prefix: str = Field(
        default="brsapi:budget",
        description="Redis key prefix for the persistent budget governor counters (daily, 5min, block)",
    )
    budget_state_file: str = Field(
        default="",
        description="JSON file used by the budget governor when Redis is unavailable (empty = json/brsapi/budget_state.json)",
    )
    budget_block_cooldown_seconds: int = Field(
        default=900, ge=0,
        description="Seconds to reject ALL live BrsApi calls after an HTTP 302 heavy-file redirect (anti re-block cooldown)",
    )

    # Candlestick full-market backfill (brsapi_candlesticks_all job)
    # The global rate limiter (1000 req/5min, 4000/day default) is the only
    # real gate — the artificial per-request delay is kept near zero (0.2s
    # politeness) so a full-market run completes as fast as the plan allows.
    candle_daily_max_symbols: int = Field(
        default=1000, ge=0,
        description="Max symbols processed per candlestick backfill run (0 = all)",
    )
    candle_req_delay: float = Field(
        default=0.2, ge=0,
        description="Seconds between Candlestick API requests — total rate is still bounded by the global 5-min (1000) and daily (4000) caps",
    )

    # Shareholder full-market backfill (brsapi_shareholders_all job)
    # The Shareholder endpoint allows 2 req/10s (12 req/min), so the daily
    # run is bounded to a chunk of symbols per day; the backfill resumes with
    # the still-missing symbols on subsequent days.
    shareholder_daily_max_symbols: int = Field(
        default=1000, ge=0,
        description="Max symbols processed per shareholder backfill run (0 = all)",
    )
    shareholder_req_delay: float = Field(
        default=5.0, ge=0,
        description="Seconds between Shareholder API requests — total rate is still bounded by the global 5-min (1000) and daily (4000) caps",
    )

    # History price full-market backfill (brsapi_history_price_all job)
    # One request per symbol against the TSETMC_History endpoint (4 req/10s),
    # bounded to a chunk per day like the shareholder backfill.
    history_price_daily_max_symbols: int = Field(
        default=500, ge=0,
        description="Max symbols processed per history-price backfill run (0 = all)",
    )
    history_price_req_delay: float = Field(
        default=5.0, ge=0,
        description="Seconds between History-Price API requests — total rate is still bounded by the global 5-min (1000) and daily (4000) caps",
    )

    # History real/legal full-market backfill (brsapi_history_real_legal_all job)
    history_real_legal_daily_max_symbols: int = Field(
        default=500, ge=0,
        description="Max symbols processed per history-real-legal backfill run (0 = all)",
    )
    history_real_legal_req_delay: float = Field(
        default=5.0, ge=0,
        description="Seconds between History-RealLegal API requests — total rate is still bounded by the global 5-min (1000) and daily (4000) caps",
    )

    # Symbol detail full-market refresh (brsapi_symbol_details_all job)
    # Symbol.php allows 3 req/10s (18 req/min), so the nightly refresh of the
    # whole market is chunked per day exactly like the shareholder/history
    # backfills. Runs every night at 21:00 — after all the after-close jobs
    # have finished, so the quota is not hammered at the same instant.
    symbol_detail_daily_max_symbols: int = Field(
        default=1000, ge=0,
        description="Max symbols processed per symbol-detail refresh run (0 = all)",
    )
    symbol_detail_req_delay: float = Field(
        default=4.0, ge=0,
        description="Seconds between Symbol.php API requests — total rate is still bounded by the global 5-min (1000) and daily (4000) caps",
    )


_brsapi_settings: BrsApiSettings | None = None


def get_brsapi_settings() -> BrsApiSettings:
    global _brsapi_settings
    if _brsapi_settings is None:
        _brsapi_settings = BrsApiSettings()
    return _brsapi_settings


settings = get_brsapi_settings()
