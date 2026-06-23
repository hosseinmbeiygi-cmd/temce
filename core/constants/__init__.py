from __future__ import annotations

from enum import StrEnum


class MarketType(StrEnum):
    BOURS = "bours"
    FARABOURS = "farabours"
    PAYEH = "payeh"
    OPTION = "option"
    FUTURES = "futures"
    ETF = "etf"


class AssetClass(StrEnum):
    EQUITY = "equity"
    BOND = "bond"
    COMMODITY = "commodity"
    CURRENCY = "currency"
    DERIVATIVE = "derivative"
    FUND = "fund"


class InstrumentStatus(StrEnum):
    ACTIVE = "active"
    SUSPENDED = "suspended"
    HALTED = "halted"
    DELISTED = "delisted"
    UNKNOWN = "unknown"


class OrderSide(StrEnum):
    BUY = "buy"
    SELL = "sell"


class OrderType(StrEnum):
    MARKET = "market"
    LIMIT = "limit"
    STOP_LOSS = "stop_loss"
    STOP_LIMIT = "stop_limit"


class TimeFrame(StrEnum):
    M1 = "1m"
    M5 = "5m"
    M15 = "15m"
    M30 = "30m"
    H1 = "1h"
    D1 = "1d"
    W1 = "1w"
    M1_MONTH = "1M"


class SignalType(StrEnum):
    BULLISH = "bullish"
    BEARISH = "bearish"
    NEUTRAL = "neutral"
    STRONG_BUY = "strong_buy"
    STRONG_SELL = "strong_sell"


class RecommendationAction(StrEnum):
    BUY = "buy"
    SELL = "sell"
    HOLD = "hold"
    ACCUMULATE = "accumulate"
    REDUCE = "reduce"


class ModelStage(StrEnum):
    DEVELOPMENT = "development"
    STAGING = "staging"
    PRODUCTION = "production"
    ARCHIVED = "archived"
    DEPRECATED = "deprecated"


class JobStatus(StrEnum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    RETRYING = "retrying"


class DataSource(StrEnum):
    TSETMC = "tsetmc"
    CODAL = "codal"
    RSS = "rss"
    MANUAL = "manual"
    FILE = "file"
    BROKER = "broker"
    EXTERNAL_API = "external_api"


class ProviderHealth(StrEnum):
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    DOWN = "down"
    UNKNOWN = "unknown"


CURRENCY_PAIRS = ("USD_IRR", "EUR_IRR", "GBP_IRR", "TRY_IRR", "AED_IRR")
COMMODITIES = ("gold", "oil", "copper", "steel", "cement")
SECTOR_GROUPS = (
    "financial",
    "petrochemical",
    "metal",
    "pharmaceutical",
    "automotive",
    "construction",
    "food",
    "insurance",
    "holding",
)

IRAN_MARKET_OPEN = "09:00"
IRAN_MARKET_CLOSE = "12:30"
IRAN_TIMEZONE = "Asia/Tehran"

MAX_PAGE_SIZE = 500
DEFAULT_PAGE_SIZE = 50
CACHE_TTL_DEFAULT = 300
CACHE_TTL_QUOTE = 10
CACHE_TTL_INSTRUMENT = 3600
