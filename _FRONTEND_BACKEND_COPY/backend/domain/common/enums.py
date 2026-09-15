from __future__ import annotations

from enum import StrEnum


class Currency(StrEnum):
    IRR = "irr"
    USD = "usd"
    EUR = "eur"
    GBP = "gbp"
    TRY = "try"
    AED = "aed"


class OrderStatus(StrEnum):
    PENDING = "pending"
    OPEN = "open"
    FILLED = "filled"
    PARTIALLY_FILLED = "partially_filled"
    CANCELLED = "cancelled"
    REJECTED = "rejected"
    EXPIRED = "expired"


class TradeSide(StrEnum):
    BUY = "buy"
    SELL = "sell"
    UNKNOWN = "unknown"


class PriceAdjustment(StrEnum):
    NONE = "none"
    SPLIT = "split"
    DIVIDEND = "dividend"
    CAPITAL_INCREASE = "capital_increase"
    ALL = "all"


class ConfidenceLevel(StrEnum):
    VERY_LOW = "very_low"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    VERY_HIGH = "very_high"


class RiskLevel(StrEnum):
    VERY_LOW = "very_low"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    VERY_HIGH = "very_high"


class Frequency(StrEnum):
    TICK = "tick"
    INTRADAY = "intraday"
    DAILY = "daily"
    WEEKLY = "weekly"
    MONTHLY = "monthly"
    QUARTERLY = "quarterly"
    YEARLY = "yearly"
