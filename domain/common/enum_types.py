from __future__ import annotations

from enum import StrEnum


class MarketType(StrEnum):
    BOURS = "bours"
    STOCK = "stock"
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
    MONTHLY = "1M"


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


class JobStatus(StrEnum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    RETRYING = "retrying"


class TimeSeriesGranularity(StrEnum):
    TICK = "tick"
    MINUTE = "minute"
    HOUR = "hour"
    DAY = "day"
    WEEK = "week"
    MONTH = "month"
